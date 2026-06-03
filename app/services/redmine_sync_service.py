from __future__ import annotations

import base64
import binascii
import html
import mimetypes
import os
import re
import uuid
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Awaitable, Callable

import anyio
from fastapi import HTTPException

from app.controllers.system_setting import system_setting_controller
from app.core.redis_client import execute_redis
from app.log import logger
from app.models.admin import Ticket, TicketActionLog, TicketAttachment
from app.models.enums import TicketActionType, TicketStatus
from app.services.redmine_client import RedmineClient
from app.settings import settings

RedisExecutor = Callable[..., Awaitable[Any]]


class RedmineSyncService:
    async def push_ticket(
        self,
        ticket: Ticket,
        *,
        operator_id: int,
        note: str | None = None,
        project_id: str | None = None,
        tracker_id: int | None = None,
        priority_id: int | None = None,
        assigned_to_id: int | None = None,
        project_phase: str | None = None,
        os_value: str | None = None,
    ) -> dict:
        config = await self._config()
        client = RedmineClient(config)
        now = datetime.now()
        try:
            description, uploads = await self._sync_content(ticket, client)
            if ticket.redmine_issue_id:
                update_payload = {
                    "subject": self._subject(ticket),
                    "description": description,
                    "notes": note or f"工单 {ticket.ticket_no} 手动同步到 Redmine",
                }
                if uploads:
                    update_payload["uploads"] = uploads
                result = await client.update_issue(
                    int(ticket.redmine_issue_id),
                    update_payload,
                )
                issue_id = int(ticket.redmine_issue_id)
            else:
                result = await client.create_issue(
                    self._create_payload(
                        ticket,
                        config,
                        description=description,
                        project_id=project_id,
                        tracker_id=tracker_id,
                        priority_id=priority_id,
                        assigned_to_id=assigned_to_id,
                        project_phase=project_phase,
                        os_value=os_value,
                        uploads=uploads,
                    )
                )
                issue_id = int(self._get_value(result, "id") or self._get_value(self._get_value(result, "issue") or {}, "id"))
                if not issue_id:
                    raise HTTPException(status_code=502, detail="Redmine 创建成功但未返回 Issue ID")

            await self._save_success(ticket, config=config, issue_id=issue_id, now=now)
            return await ticket.to_dict()
        except Exception as exc:
            if isinstance(exc, HTTPException):
                await self._save_failure(ticket, str(exc.detail), now=now)
                raise
            await self._save_failure(ticket, str(exc), now=now)
            raise

    async def pull_ticket(self, ticket: Ticket, *, operator_id: int) -> dict:
        if not ticket.redmine_issue_id:
            raise HTTPException(status_code=400, detail="工单尚未同步到 Redmine")
        config = await self._config()
        client = RedmineClient(config)
        now = datetime.now()
        try:
            issue = await client.get_issue(int(ticket.redmine_issue_id), include="journals,attachments")
            status = self._get_value(issue, "status")
            ticket.redmine_status_id = self._get_value(status, "id") if status is not None else None
            ticket.redmine_status_name = self._get_value(status, "name") if status is not None else None
            ticket.redmine_last_updated_on = self._parse_datetime(self._get_value(issue, "updated_on"))
            ticket.redmine_sync_status = "success"
            ticket.redmine_sync_error = None
            ticket.redmine_synced_at = now
            await ticket.save()
            journals = await self._pending_journal_notes(ticket, issue)
            attachment_map = await self._sync_redmine_attachments(
                ticket,
                issue,
                client=client,
                operator_id=operator_id,
                filenames=self._journal_image_filenames(journals),
            )
            await self._sync_journal_notes(ticket, journals, operator_id=operator_id, attachment_map=attachment_map)
            return await ticket.to_dict()
        except Exception as exc:
            if isinstance(exc, HTTPException):
                await self._save_failure(ticket, str(exc.detail), now=now)
                raise
            await self._save_failure(ticket, str(exc), now=now)
            raise

    async def _config(self) -> dict:
        config = await system_setting_controller.get_full_dict()
        if not config.get("redmine_enabled"):
            raise HTTPException(status_code=400, detail="Redmine 同步未启用")
        required = ["redmine_base_url", "redmine_api_key", "redmine_project_id"]
        missing = [key for key in required if not config.get(key)]
        if missing:
            raise HTTPException(status_code=400, detail=f"Redmine 配置不完整: {', '.join(missing)}")
        return config

    def _create_payload(
        self,
        ticket: Ticket,
        config: dict,
        *,
        description: str,
        project_id: str | None = None,
        tracker_id: int | None = None,
        priority_id: int | None = None,
        assigned_to_id: int | None = None,
        project_phase: str | None = None,
        os_value: str | None = None,
        uploads: list[dict[str, str]] | None = None,
    ) -> dict:
        payload = {
            "project_id": self._project_id(project_id or config.get("redmine_project_id")),
            "tracker_id": tracker_id or self._optional_int(config.get("redmine_tracker_id")),
            "priority_id": priority_id or self._optional_int(config.get("redmine_priority_id")),
            "assigned_to_id": assigned_to_id or self._optional_int(config.get("redmine_assigned_to_id")),
            "subject": self._subject(ticket),
            "description": description,
        }
        custom_fields = self._custom_fields(ticket, config, project_phase=project_phase, os_value=os_value)
        if custom_fields:
            payload["custom_fields"] = custom_fields
        if uploads:
            payload["uploads"] = uploads
        return {key: value for key, value in payload.items() if value is not None and value != ""}

    def _custom_fields(
        self,
        ticket: Ticket,
        config: dict,
        *,
        project_phase: str | None = None,
        os_value: str | None = None,
    ) -> list[dict]:
        fields = []
        project_phase_field_id = self._optional_int(config.get("redmine_project_phase_field_id"))
        project_phase_value = str(project_phase or getattr(ticket, "project_phase", None) or "").strip()
        if project_phase_field_id and project_phase_value:
            fields.append({"id": project_phase_field_id, "value": project_phase_value})

        os_field_id = self._optional_int(config.get("redmine_os_field_id"))
        os_text = str(os_value or "").strip()
        if os_field_id and os_text:
            fields.append({"id": os_field_id, "value": os_text})
        return fields

    def _subject(self, ticket: Ticket) -> str:
        project_name = self._text(getattr(ticket, "company_name", None))
        title = self._text(getattr(ticket, "title", None))
        return f"【{project_name}】{title}"

    async def _sync_content(self, ticket: Ticket, client: RedmineClient) -> tuple[str, list[dict[str, str]]]:
        image_uploads, image_names = await self._upload_inline_images(ticket, client)
        attachment_uploads = await self._upload_attachments(ticket, client)
        description = await self._description(ticket, image_names=image_names)
        return description, [*image_uploads, *attachment_uploads]

    async def _description(self, ticket: Ticket, *, image_names: dict[str, str] | None = None) -> str:
        attachments = await self._attachments(ticket)
        lines = [
            f"工单编号：{ticket.ticket_no}",
            f"项目名称：{self._text(getattr(ticket, 'company_name', None))}",
            f"影响范围：{self._text(getattr(ticket, 'impact_scope', None))}",
            f"问题分类：{self._text(getattr(ticket, 'category', None))}",
            f"联系人：{self._text(getattr(ticket, 'contact_name', None))}",
            f"邮箱：{self._text(getattr(ticket, 'email', None))}",
            f"电话：{self._text(getattr(ticket, 'phone', None))}",
            "",
            "问题描述：",
            self._plain_description(getattr(ticket, "description", None), image_names=image_names),
            "",
            "附件：",
            "\n".join(attachments) if attachments else "-",
        ]
        return "\n".join(lines)

    async def _attachments(self, ticket: Ticket) -> list[str]:
        attachments = await self._attachment_items(ticket)
        result = []
        for item in attachments:
            name = self._attachment_name(item)
            if name:
                result.append(name)
        return result

    async def _attachment_items(self, ticket: Ticket) -> list[Any]:
        attachments = getattr(ticket, "attachments", None)
        if attachments is None:
            try:
                attachments = await TicketAttachment.filter(ticket_id=ticket.id).order_by("id")
            except Exception:
                attachments = []
        return list(attachments or [])

    async def _upload_attachments(self, ticket: Ticket, client: RedmineClient) -> list[dict[str, str]]:
        uploads = []
        for item in await self._attachment_items(ticket):
            filename = self._attachment_name(item)
            file_path = self._get_value(item, "file_path")
            if not filename or not file_path:
                continue
            abs_path = self._attachment_abs_path(str(file_path))
            if not abs_path:
                continue
            content = await anyio.to_thread.run_sync(abs_path.read_bytes)
            content_type = str(self._get_value(item, "mime_type") or mimetypes.guess_type(filename)[0] or "application/octet-stream")
            token = await client.upload(filename, content, content_type=content_type)
            uploads.append({"token": token, "filename": filename, "content_type": content_type})
        return uploads

    async def _upload_inline_images(self, ticket: Ticket, client: RedmineClient) -> tuple[list[dict[str, str]], dict[str, str]]:
        uploads = []
        image_names = {}
        for index, (src, content_type, content) in enumerate(self._data_uri_images(getattr(ticket, "description", None)), start=1):
            if src in image_names:
                continue
            ext = self._image_extension(content_type)
            filename = f"{self._safe_filename_part(getattr(ticket, 'ticket_no', None))}-image-{index}.{ext}"
            token = await client.upload(filename, content, content_type=content_type)
            uploads.append({"token": token, "filename": filename, "content_type": content_type})
            image_names[src] = filename
        return uploads, image_names

    @staticmethod
    def _attachment_name(item: Any) -> str:
        name = RedmineSyncService._get_value(item, "origin_name") or RedmineSyncService._get_value(item, "file_name") or RedmineSyncService._get_value(item, "filename")
        if not name:
            name = RedmineSyncService._get_value(item, "file_path")
        return str(name or "").strip()

    @staticmethod
    def _attachment_abs_path(file_path: str) -> Path | None:
        path = Path(file_path)
        if not path.is_absolute():
            path = Path(settings.UPLOAD_DIR) / file_path
        try:
            resolved = path.resolve()
        except OSError:
            return None
        if not resolved.is_file():
            return None
        return resolved

    @staticmethod
    def _data_uri_images(value: Any) -> list[tuple[str, str, bytes]]:
        text = str(value or "")
        result = []
        pattern = re.compile(r"data:(image/[a-zA-Z0-9.+-]+);base64,([A-Za-z0-9+/=\r\n]+)")
        for match in pattern.finditer(text):
            src = match.group(0)
            content_type = match.group(1).lower()
            payload = re.sub(r"\s+", "", match.group(2))
            try:
                content = base64.b64decode(payload, validate=True)
            except (binascii.Error, ValueError):
                continue
            if content:
                result.append((src, content_type, content))
        return result

    @staticmethod
    def _image_extension(content_type: str) -> str:
        mapping = {
            "image/jpeg": "jpg",
            "image/png": "png",
            "image/gif": "gif",
            "image/webp": "webp",
            "image/bmp": "bmp",
        }
        return mapping.get(content_type.lower(), "png")

    @staticmethod
    def _safe_filename_part(value: Any) -> str:
        text = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value or "").strip()).strip(".-")
        return text or "ticket"

    @staticmethod
    def _plain_description(value: Any, *, image_names: dict[str, str] | None = None) -> str:
        text = str(value or "")
        if not text:
            return ""
        image_tokens: list[str] = []
        image_names = image_names or {}

        def keep_image(match: re.Match) -> str:
            tag = match.group(0)
            src_match = re.search(r"""src\s*=\s*["']([^"']+)["']""", tag, flags=re.IGNORECASE)
            if not src_match:
                return ""
            token = f"__REDMINE_IMAGE_{len(image_tokens)}__"
            src = html.unescape(src_match.group(1)).strip()
            image_tokens.append(f"![]({image_names.get(src, src)})")
            return f"\n{token}\n"

        text = re.sub(r"<img\b[^>]*>", keep_image, text, flags=re.IGNORECASE)
        text = re.sub(r"</?(p|div|section|article|li|ul|ol|h[1-6])\b[^>]*>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
        text = html.unescape(text)
        for index, image in enumerate(image_tokens):
            text = text.replace(f"__REDMINE_IMAGE_{index}__", image)
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
        return "\n".join(line for line in lines if line)

    @staticmethod
    def _text(value: Any) -> str:
        text = str(value or "").strip()
        return text or "-"

    async def _save_success(self, ticket: Ticket, *, config: dict, issue_id: int, now: datetime) -> None:
        ticket.redmine_issue_id = issue_id
        ticket.redmine_issue_url = f"{str(config.get('redmine_base_url')).rstrip('/')}/issues/{issue_id}"
        ticket.redmine_sync_status = "success"
        ticket.redmine_sync_error = None
        ticket.redmine_synced_at = now
        await ticket.save()

    async def _save_failure(self, ticket: Ticket, error: str, *, now: datetime) -> None:
        ticket.redmine_sync_status = "failed"
        ticket.redmine_sync_error = error[:2000]
        ticket.redmine_synced_at = now
        await ticket.save()

    async def _sync_redmine_attachments(
        self,
        ticket: Ticket,
        issue: Any,
        *,
        client: RedmineClient,
        operator_id: int,
        filenames: set[str] | None = None,
    ) -> dict[str, TicketAttachment]:
        filenames = filenames or set()
        if not filenames:
            return {}
        result = {}
        for attachment in self._iter_values(self._get_value(issue, "attachments")):
            filename = self._attachment_name(attachment)
            if not filename:
                continue
            if filename not in filenames:
                continue
            attachment_id = self._get_value(attachment, "id")
            marker = f"redmine-{ticket.redmine_issue_id}-{attachment_id}" if attachment_id is not None else ""
            existing = None
            if marker:
                existing = await TicketAttachment.filter(ticket_id=ticket.id, file_path__contains=marker).first()
            if existing:
                result[filename] = existing
                continue
            try:
                content = await client.download_attachment(attachment)
            except Exception:
                continue
            if not content:
                continue
            saved = await self._save_redmine_attachment(
                ticket=ticket,
                filename=filename,
                content=content,
                content_type=self._redmine_attachment_content_type(attachment, filename),
                operator_id=operator_id,
                marker=marker,
            )
            result[filename] = saved
        return result

    async def _save_redmine_attachment(
        self,
        *,
        ticket: Ticket,
        filename: str,
        content: bytes,
        content_type: str,
        operator_id: int,
        marker: str,
    ) -> TicketAttachment:
        safe_filename = os.path.basename(filename) or "redmine-attachment"
        ext = Path(safe_filename).suffix.lower().lstrip(".") or "bin"
        now = datetime.now()
        rel_dir = os.path.join("tickets", now.strftime("%Y"), now.strftime("%m"), now.strftime("%d"))
        abs_dir = Path(settings.UPLOAD_DIR) / rel_dir
        await anyio.to_thread.run_sync(abs_dir.mkdir, 0o777, True, True)
        stored_prefix = marker or f"redmine-{ticket.redmine_issue_id}-{uuid.uuid4().hex}"
        stored_name = f"{stored_prefix}-{uuid.uuid4().hex}.{ext}"
        rel_path = os.path.join(rel_dir, stored_name).replace("\\", "/")
        abs_path = Path(settings.UPLOAD_DIR) / rel_path
        await anyio.to_thread.run_sync(abs_path.write_bytes, content)
        return await TicketAttachment.create(
            ticket_id=ticket.id,
            origin_name=safe_filename,
            file_path=rel_path,
            file_size=len(content),
            mime_type=content_type,
            uploader_id=operator_id,
        )

    def _redmine_attachment_content_type(self, attachment: Any, filename: str) -> str:
        return str(
            self._get_value(attachment, "content_type")
            or self._get_value(attachment, "mime_type")
            or mimetypes.guess_type(filename)[0]
            or "application/octet-stream"
        )

    async def _pending_journal_notes(self, ticket: Ticket, issue: Any) -> list[dict[str, Any]]:
        result = []
        for journal in self._iter_values(self._get_value(issue, "journals")):
            journal_id = self._get_value(journal, "id")
            marker = f"<!-- redmine-journal:{journal_id} -->" if journal_id is not None else ""
            notes = str(self._get_value(journal, "notes") or "").strip()
            if not notes:
                continue
            if marker and await TicketActionLog.filter(ticket_id=ticket.id, comment__contains=marker).exists():
                continue
            result.append({"journal": journal, "marker": marker, "notes": notes})
        return result

    def _journal_image_filenames(self, journals: list[dict[str, Any]]) -> set[str]:
        result = set()
        for item in journals:
            for match in re.finditer(r"!([^!\r\n]+)!", str(item.get("notes") or "")):
                filename = html.unescape(match.group(1)).strip()
                if filename:
                    result.add(filename)
        return result

    async def _sync_journal_notes(
        self,
        ticket: Ticket,
        journals: list[dict[str, Any]],
        *,
        operator_id: int,
        attachment_map: dict[str, TicketAttachment] | None = None,
    ) -> int:
        attachment_map = attachment_map or {}
        created_count = 0
        for item in journals:
            journal = item["journal"]
            marker = item["marker"]
            notes = item["notes"]

            user = self._get_value(journal, "user")
            author = self._get_value(user, "name") or self._get_value(user, "login") or self._get_value(user, "id") or "-"
            created_on = self._parse_datetime(self._get_value(journal, "created_on"))
            created_text = created_on.strftime("%Y-%m-%d %H:%M:%S") if created_on else "-"
            notes = self._format_redmine_note_content(notes, attachment_map)
            comment = "\n".join(
                part
                for part in [
                    marker,
                    f"Redmine备注人：{author}",
                    f"Redmine备注时间：{created_text}",
                    f"备注内容：{notes}",
                ]
                if part != ""
            )
            await TicketActionLog.create(
                ticket_id=ticket.id,
                action=TicketActionType.TECH_NOTE,
                from_status=ticket.status,
                to_status=ticket.status,
                operator_id=operator_id,
                comment=comment,
            )
            created_count += 1
        return created_count

    def _format_redmine_note_content(self, notes: str, attachment_map: dict[str, TicketAttachment]) -> str:
        text = html.escape(notes)
        text = re.sub(r"\r\n|\r|\n", "<br>", text)

        def replace_image(match: re.Match) -> str:
            filename = html.unescape(match.group(1)).strip()
            attachment = attachment_map.get(filename)
            if not attachment:
                return html.escape(match.group(0))
            return (
                f'<br><img src="/api/v1/ticket/attachment/download?attachment_id={attachment.id}" '
                f'alt="{html.escape(filename, quote=True)}" loading="lazy" decoding="async"><br>'
            )

        return re.sub(r"!([^!\r\n]+)!", replace_image, text)

    @staticmethod
    def _get_value(value: Any, key: str) -> Any:
        if value is None:
            return None
        if isinstance(value, dict):
            return value.get(key)
        return getattr(value, key, None)

    @staticmethod
    def _iter_values(value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, (list, tuple)):
            return list(value)
        try:
            return list(value)
        except TypeError:
            return []

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value
        if not value:
            return None
        text = str(value).replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        if value in {None, ""}:
            return None
        return int(value)

    @staticmethod
    def _project_id(value: Any) -> int | str | None:
        if value in {None, ""}:
            return None
        text = str(value).strip()
        if not text:
            return None
        return int(text) if text.isdigit() else text


redmine_sync_service = RedmineSyncService()


class RedmineAutoPullScheduler:
    LOCK_KEY = "redmine:auto_pull:lock"
    LOCK_TTL_SECONDS = 30 * 60
    MAX_BATCH_SIZE = 100

    def __init__(
        self,
        *,
        service: RedmineSyncService | None = None,
        config_controller: Any | None = None,
        ticket_model: Any | None = None,
        redis_executor: RedisExecutor | None = None,
    ) -> None:
        self.service = service or redmine_sync_service
        self.config_controller = config_controller or system_setting_controller
        self.ticket_model = ticket_model or Ticket
        self.redis_executor = redis_executor or execute_redis
        self._task: asyncio.Task | None = None
        self._stopping = asyncio.Event()
        self._local_lock = asyncio.Lock()

    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stopping = asyncio.Event()
        self._task = asyncio.create_task(self._run_loop())
        logger.info("[redmine.auto_pull.scheduler] started")

    async def stop(self) -> None:
        self._stopping.set()
        if not self._task:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        finally:
            self._task = None
            logger.info("[redmine.auto_pull.scheduler] stopped")

    async def _run_loop(self) -> None:
        while not self._stopping.is_set():
            sleep_seconds = 30 * 60
            try:
                config = await self.config_controller.get_full_dict()
                sleep_seconds = self._interval_seconds(config)
                if not config.get("redmine_enabled") or not config.get("redmine_auto_pull_enabled"):
                    await self._sleep_or_stop(sleep_seconds)
                    continue
                await self.run_once(config=config)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception("[redmine.auto_pull.scheduler] run_failed error={}", str(exc))
            if await self._sleep_or_stop(sleep_seconds):
                return

    async def run_once(self, *, config: dict | None = None) -> dict | None:
        config = config or await self.config_controller.get_full_dict()
        if not config.get("redmine_enabled") or not config.get("redmine_auto_pull_enabled"):
            return {"checked": 0, "pulled": 0, "failed": 0, "enabled": False}

        token = self._lock_token()
        acquired = await self._acquire_distributed_lock(token)
        if acquired is False:
            logger.info("[redmine.auto_pull.scheduler] skip_run lock_held")
            return None

        if acquired is None:
            if self._local_lock.locked():
                logger.info("[redmine.auto_pull.scheduler] skip_run local_lock_held")
                return None
            async with self._local_lock:
                return await self._pull_batch(config)

        try:
            return await self._pull_batch(config)
        finally:
            await self._release_distributed_lock(token)

    async def _pull_batch(self, config: dict) -> dict:
        ticket_statuses = self._ticket_statuses(config)
        query = (
            self.ticket_model.exclude(redmine_issue_id__isnull=True)
            .filter(status__in=ticket_statuses)
            .order_by("redmine_synced_at", "id")
            .limit(self.MAX_BATCH_SIZE)
        )
        tickets = await query
        checked = len(tickets)
        pulled = 0
        failed = 0
        for ticket in tickets:
            try:
                await self.service.pull_ticket(ticket, operator_id=self._operator_id(ticket))
                pulled += 1
            except Exception as exc:
                failed += 1
                logger.warning(
                    "[redmine.auto_pull.scheduler] pull_failed ticket_id={} redmine_issue_id={} error={}",
                    getattr(ticket, "id", None),
                    getattr(ticket, "redmine_issue_id", None),
                    str(exc),
                )
        if checked:
            logger.info("[redmine.auto_pull.scheduler] batch_done checked={} pulled={} failed={}", checked, pulled, failed)
        return {"checked": checked, "pulled": pulled, "failed": failed, "enabled": True}

    def _ticket_statuses(self, config: dict) -> list[str]:
        valid_statuses = {item.value for item in TicketStatus}
        result = []
        for item in config.get("redmine_auto_pull_ticket_statuses") or []:
            status = str(item or "").strip()
            if status in valid_statuses and status not in result:
                result.append(status)
        return result or [TicketStatus.TECH_PROCESSING.value]

    def _operator_id(self, ticket: Any) -> int:
        for attr in ("tech_id", "reviewer_id", "submitter_id"):
            value = getattr(ticket, attr, None)
            if value:
                return int(value)
        return 0

    def _interval_seconds(self, config: dict) -> int:
        try:
            minutes = int(config.get("redmine_auto_pull_interval_minutes") or 30)
        except Exception:
            minutes = 30
        minutes = min(1440, max(1, minutes))
        return minutes * 60

    async def _acquire_distributed_lock(self, token: str) -> bool | None:
        try:
            result = await self.redis_executor(
                "set",
                self.LOCK_KEY,
                token,
                ex=self.LOCK_TTL_SECONDS,
                nx=True,
            )
            return bool(result)
        except Exception as exc:
            logger.warning("[redmine.auto_pull.scheduler] redis_lock_unavailable fallback=local error={}", str(exc))
            return None

    async def _release_distributed_lock(self, token: str) -> None:
        script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        end
        return 0
        """
        try:
            await self.redis_executor("eval", script, 1, self.LOCK_KEY, token)
        except Exception as exc:
            logger.warning("[redmine.auto_pull.scheduler] release_lock_failed error={}", str(exc))

    async def _sleep_or_stop(self, seconds: int) -> bool:
        try:
            await asyncio.wait_for(self._stopping.wait(), timeout=max(1, seconds))
            return True
        except TimeoutError:
            return False

    def _lock_token(self) -> str:
        return f"{id(self)}:{datetime.now().isoformat(timespec='microseconds')}"


redmine_auto_pull_scheduler = RedmineAutoPullScheduler(service=redmine_sync_service)
