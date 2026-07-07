import asyncio
import hashlib
import os
import re
import shutil
import uuid
from datetime import datetime
from mimetypes import guess_type
from time import perf_counter

from fastapi import HTTPException, UploadFile
from tortoise.expressions import Q

from app.log import logger
from app.controllers.mail import mail_controller
from app.controllers.system_setting import system_setting_controller
from app.controllers.user import user_controller
from app.controllers.webdav import webdav_controller
from app.models.admin import Dept, DeptClosure, Ticket, TicketActionLog, TicketAttachment, User
from app.models.enums import TicketActionType, TicketStatus
from app.settings import settings
from app.utils.file_signature import detect_file_type, normalize_ext
from app.utils.http_headers import build_download_content_disposition


class TicketController:
    _ROLE_NOTIFY_MAP = {
        "用户": "用户",
        "渠道商": "代理商",
        "代理商": "代理商",
        "客服": "客服",
        "技术": "技术",
        "管理员": "客服",
    }

    @staticmethod
    def _status_notify_recipients(status: TicketStatus, ticket: Ticket) -> list[int]:
        if status == TicketStatus.PENDING_REVIEW:
            return []
        if status in {TicketStatus.TECH_PROCESSING, TicketStatus.FIELD_VERIFICATION}:
            return [ticket.tech_id] if ticket.tech_id else []
        if status in {TicketStatus.CS_REJECTED, TicketStatus.TECH_REJECTED, TicketStatus.PENDING_CLOSE, TicketStatus.DONE}:
            return [ticket.submitter_id] if ticket.submitter_id else []
        return []

    async def _notify_ticket_status_if_needed(self, *, ticket: Ticket, operator_id: int) -> None:
        setting = await system_setting_controller.get_safe_dict()
        notify_map = setting.get("ticket_notify_by_role") or {}
        all_users = await User.filter(is_active=True).prefetch_related("roles")
        recipients: list[User] = []
        current_status = str(ticket.status)

        for item in all_users:
            if item.id == operator_id or not item.email:
                continue
            role_names = [role.name for role in await item.roles]
            if item.is_superuser:
                role_names.append("管理员")

            normalized_roles = {self._ROLE_NOTIFY_MAP.get(role, role) for role in role_names}
            should_notify = False
            for role_name in normalized_roles:
                statuses = notify_map.get(role_name) or []
                if current_status in statuses:
                    should_notify = True
                    break
            if not should_notify:
                continue

            if current_status in {
                TicketStatus.CS_REJECTED.value,
                TicketStatus.TECH_REJECTED.value,
                TicketStatus.PENDING_CLOSE.value,
                TicketStatus.DONE.value,
            }:
                if item.id != ticket.submitter_id:
                    continue
            if (
                current_status in {TicketStatus.TECH_PROCESSING.value, TicketStatus.FIELD_VERIFICATION.value}
                and ticket.tech_id
                and item.id != ticket.tech_id
            ):
                continue
            recipients.append(item)

        if not recipients:
            return

        operator = await User.filter(id=operator_id).first()
        operator_name = (operator.alias or operator.username) if operator else str(operator_id)
        for target in recipients:
            if not target.email:
                continue
            try:
                await mail_controller.send_ticket_status_notice(
                    ticket=ticket,
                    to_user=target,
                    status=ticket.status,
                    operator_name=operator_name,
                )
            except Exception:
                logger.warning(
                    "[ticket.notify] send_failed ticket_id={} status={} to_user_id={}",
                    ticket.id,
                    ticket.status,
                    target.id,
                    exc_info=True,
                )
    @staticmethod
    def _sanitize_rich_html(value: str | None) -> str:
        text = str(value or "")
        if not text:
            return ""

        # Strip dangerous tags first
        text = re.sub(r"<\s*(script|iframe|object|embed|link|style)[^>]*>.*?<\s*/\s*\1\s*>", "", text, flags=re.I | re.S)
        text = re.sub(r"<\s*(script|iframe|object|embed|link|style)[^>]*?/\s*>", "", text, flags=re.I | re.S)

        # Remove event handlers like onclick/onerror
        text = re.sub(r"\son[a-zA-Z]+\s*=\s*([\"']).*?\1", "", text, flags=re.I | re.S)
        text = re.sub(r"\son[a-zA-Z]+\s*=\s*[^\s>]+", "", text, flags=re.I)

        # Remove javascript: href/src
        text = re.sub(r"\s(href|src)\s*=\s*([\"'])\s*javascript:[^\2]*\2", "", text, flags=re.I)
        text = re.sub(r"\s(href|src)\s*=\s*javascript:[^\s>]+", "", text, flags=re.I)
        return text

    @staticmethod
    def _next_ticket_no() -> str:
        return f"TK{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"

    @staticmethod
    def _normalize_extensions(items: list[str] | None) -> list[str]:
        normalized: list[str] = []
        for item in items or []:
            value = str(item or "").strip().lower().lstrip(".")
            if value and value not in normalized:
                normalized.append(value)
        return normalized

    async def _write_action(
        self,
        *,
        ticket_id: int,
        action: TicketActionType,
        from_status: TicketStatus | None,
        to_status: TicketStatus,
        operator_id: int,
        comment: str | None,
    ) -> None:
        await TicketActionLog.create(
            ticket_id=ticket_id,
            action=action,
            from_status=from_status,
            to_status=to_status,
            operator_id=operator_id,
            comment=comment,
        )

    async def _bind_attachments(self, *, ticket_id: int, attachment_ids: list[int], owner_ids: list[int]) -> int:
        if not attachment_ids:
            return 0

        bound_count = await TicketAttachment.filter(
            id__in=attachment_ids,
            ticket_id=None,
            uploader_id__in=owner_ids,
        ).update(ticket_id=ticket_id)

        if bound_count < len(attachment_ids):
            logger.warning(
                "[ticket.attach] some attachments not bound ticket_id={} requested={} bound={} owners={}",
                ticket_id,
                attachment_ids,
                bound_count,
                owner_ids,
            )
            raise HTTPException(status_code=403, detail="附件不存在、已绑定或不属于当前用户")
        else:
            logger.info(
                "[ticket.attach] bound success ticket_id={} requested={} bound={} owners={}",
                ticket_id,
                attachment_ids,
                bound_count,
                owner_ids,
            )
        return bound_count

    @staticmethod
    async def _tech_related_submitter_ids(tech_id: int) -> list[int]:
        # ponytail: department table scan; split to a relation table if department count makes this hot.
        depts = await Dept.filter(is_deleted=False).all()
        dept_ids = [dept.id for dept in depts if int(tech_id) in {int(item or 0) for item in (dept.tech_ids or [])}]
        if not dept_ids:
            return []
        descendant_ids = await DeptClosure.filter(ancestor__in=dept_ids).values_list("descendant", flat=True)
        visible_dept_ids = set(dept_ids) | {int(item) for item in descendant_ids}
        return [int(item) for item in await User.filter(dept_id__in=visible_dept_ids).values_list("id", flat=True)]

    async def create_ticket(self, *, submitter_id: int, payload: dict, notify_pending_review: bool = True) -> Ticket:
        logger.info(
            "[ticket.create] start submitter_id={} project_phase={} issue_type={} impact_scope={} category={} title={}",
            submitter_id,
            payload.get("project_phase"),
            payload.get("issue_type"),
            payload.get("impact_scope"),
            payload.get("category"),
            payload.get("title"),
        )
        attachment_ids = payload.pop("attachment_ids", [])
        payload["description"] = self._sanitize_rich_html(payload.get("description"))
        logger.info("[ticket.create] parsed attachment_ids={} submitter_id={}", attachment_ids, submitter_id)
        ticket = await Ticket.create(
            ticket_no=self._next_ticket_no(),
            submitter_id=submitter_id,
            status=TicketStatus.PENDING_REVIEW,
            **payload,
        )
        if attachment_ids:
            await self._bind_attachments(ticket_id=ticket.id, attachment_ids=attachment_ids, owner_ids=[submitter_id])

        bound_rows = await TicketAttachment.filter(ticket_id=ticket.id).values("id", "uploader_id", "origin_name")
        logger.info("[ticket.create] ticket_id={} bound_attachments={}", ticket.id, bound_rows)
        await self._write_action(
            ticket_id=ticket.id,
            action=TicketActionType.SUBMIT,
            from_status=None,
            to_status=TicketStatus.PENDING_REVIEW,
            operator_id=submitter_id,
            comment=None,
        )
        if notify_pending_review:
            await self._notify_ticket_status_if_needed(ticket=ticket, operator_id=submitter_id)
        logger.info(
            "[ticket.create] success ticket_id={} ticket_no={} submitter_id={} attachment_count={}",
            ticket.id,
            ticket.ticket_no,
            submitter_id,
            len(attachment_ids),
        )
        return ticket

    async def create_ticket_with_optional_auto_review(self, *, submitter_id: int, payload: dict) -> Ticket:
        config = await system_setting_controller.get_public_config()
        auto_approve = config.get("customer_service_auto_approve_ticket", False)
        needs_cs_review = self._needs_customer_service_review(payload.get("project_phase"), config)
        ticket = await self.create_ticket(
            submitter_id=submitter_id,
            payload=payload,
            notify_pending_review=not auto_approve and needs_cs_review,
        )
        if not needs_cs_review:
            tech_user = await self._get_first_active_tech_user()
            if not tech_user:
                logger.warning("[ticket.auto_review] skipped ticket_id={} reason=no_active_tech_user", ticket.id)
                await self._notify_ticket_status_if_needed(ticket=ticket, operator_id=submitter_id)
                return ticket
            ticket.status = TicketStatus.TECH_PROCESSING
            ticket.tech_id = tech_user.id
            await ticket.save()
            await self._write_action(
                ticket_id=ticket.id,
                action=TicketActionType.TECH_START,
                from_status=TicketStatus.PENDING_REVIEW,
                to_status=TicketStatus.TECH_PROCESSING,
                operator_id=submitter_id,
                comment="无需客服审核，自动进入技术处理",
            )
            await self._notify_ticket_status_if_needed(ticket=ticket, operator_id=submitter_id)
            return ticket

        if not auto_approve:
            return ticket

        tech_user = await self._get_first_active_tech_user()
        if not tech_user:
            logger.warning("[ticket.auto_review] skipped ticket_id={} reason=no_active_tech_user", ticket.id)
            await self._notify_ticket_status_if_needed(ticket=ticket, operator_id=submitter_id)
            return ticket

        try:
            return await self.set_customer_service_review(
                ticket_id=ticket.id,
                reviewer_id=0,
                approved=True,
                comment="客服自动审批",
                tech_id=tech_user.id,
            )
        except Exception:
            logger.warning(
                "[ticket.auto_review] failed ticket_id={} tech_id={}",
                ticket.id,
                tech_user.id,
                exc_info=True,
            )
            await self._notify_ticket_status_if_needed(ticket=ticket, operator_id=submitter_id)
            return ticket

    @staticmethod
    def _needs_customer_service_review(project_phase: str | None, config: dict) -> bool:
        review_phases = set(config.get("ticket_cs_review_project_phases") or [])
        return not review_phases or project_phase in review_phases

    async def _get_first_active_tech_user(self) -> User | None:
        return await User.filter(is_active=True, roles__name="技术").order_by("id").first()

    async def get_ticket(self, ticket_id: int) -> Ticket:
        return await Ticket.get(id=ticket_id)

    async def list_tickets(self, *, page: int, page_size: int, search: Q) -> tuple[int, list[dict]]:
        start_at = perf_counter()
        query = Ticket.filter(search)
        total = await query.count()
        rows = await query.order_by("-id").offset((page - 1) * page_size).limit(page_size).values(
            "id",
            "ticket_no",
            "company_name",
            "project_phase",
            "issue_type",
            "impact_scope",
            "category",
            "contact_name",
            "phone",
            "title",
            "root_cause",
            "status",
            "redmine_issue_id",
            "redmine_issue_url",
            "redmine_sync_status",
            "redmine_sync_error",
            "redmine_synced_at",
            "redmine_last_updated_on",
            "redmine_status_id",
            "redmine_status_name",
            "redmine_closed",
            "submitter_id",
            "reviewer_id",
            "tech_id",
            "finished_at",
            "created_at",
            "updated_at",
        )

        user_ids = {
            *(row.get("submitter_id") for row in rows if row.get("submitter_id")),
            *(row.get("reviewer_id") for row in rows if row.get("reviewer_id")),
            *(row.get("tech_id") for row in rows if row.get("tech_id")),
        }
        user_map: dict[int, str] = {}
        if user_ids:
            for uid in list(user_ids):
                try:
                    basic = await user_controller.get_user_basic(int(uid))
                    user_map[int(uid)] = str(basic.get("alias") or basic.get("username") or "")
                except Exception:
                    user_map[int(uid)] = ""

        for row in rows:
            for field in ("created_at", "updated_at", "finished_at", "redmine_synced_at", "redmine_last_updated_on"):
                value = row.get(field)
                if isinstance(value, datetime):
                    row[field] = value.strftime(settings.DATETIME_FORMAT)
            row["submitter_name"] = user_map.get(row.get("submitter_id"), "")
            row["reviewer_name"] = user_map.get(row.get("reviewer_id"), "")
            row["tech_name"] = user_map.get(row.get("tech_id"), "")
        logger.info(
            "[ticket.list] page={} page_size={} total={} rows={} cost_ms={}",
            page,
            page_size,
            total,
            len(rows),
            int((perf_counter() - start_at) * 1000),
        )
        return total, rows

    async def status_summary(self, *, search: Q) -> dict[str, int]:
        query = Ticket.filter(search)
        total, pending_review, tech_processing, field_verification, pending_close, done, rejected = await asyncio.gather(
            query.count(),
            query.filter(status=TicketStatus.PENDING_REVIEW).count(),
            query.filter(status=TicketStatus.TECH_PROCESSING).count(),
            query.filter(status=TicketStatus.FIELD_VERIFICATION).count(),
            query.filter(status=TicketStatus.PENDING_CLOSE).count(),
            query.filter(status=TicketStatus.DONE).count(),
            query.filter(status__in=[TicketStatus.CS_REJECTED, TicketStatus.TECH_REJECTED]).count(),
        )
        return {
            "total": int(total or 0),
            "pending_review": int(pending_review or 0),
            "tech_processing": int(tech_processing or 0),
            "field_verification": int(field_verification or 0),
            "pending_close": int(pending_close or 0),
            "done": int(done or 0),
            "rejected": int(rejected or 0),
        }

    async def set_customer_service_review(
        self, *, ticket_id: int, reviewer_id: int, approved: bool, comment: str | None, tech_id: int | None
    ) -> Ticket:
        logger.info(
            "[ticket.cs_review] start ticket_id={} reviewer_id={} approved={} comment={}",
            ticket_id,
            reviewer_id,
            approved,
            comment,
        )
        ticket = await self.get_ticket(ticket_id)
        if ticket.status != TicketStatus.PENDING_REVIEW:
            raise HTTPException(status_code=400, detail="当前状态不可进行客服审核")

        old_status = ticket.status
        comment = self._sanitize_rich_html(comment)
        if approved:
            if not tech_id:
                raise HTTPException(status_code=400, detail="审核通过时必须指派技术处理人")
            tech_user = await User.filter(id=tech_id, is_active=True, roles__name="技术").first()
            if not tech_user:
                raise HTTPException(status_code=400, detail="请选择有效的技术处理人")
            ticket.status = TicketStatus.TECH_PROCESSING
            ticket.reviewer_id = reviewer_id
            ticket.tech_id = tech_id
            ticket.reject_reason = None
            action = TicketActionType.CS_APPROVE
        else:
            ticket.status = TicketStatus.CS_REJECTED
            ticket.reviewer_id = reviewer_id
            ticket.reject_reason = comment or "客服驳回"
            action = TicketActionType.CS_REJECT

        await ticket.save()
        await self._write_action(
            ticket_id=ticket.id,
            action=action,
            from_status=old_status,
            to_status=ticket.status,
            operator_id=reviewer_id,
            comment=comment,
        )
        await self._notify_ticket_status_if_needed(ticket=ticket, operator_id=reviewer_id)
        logger.info(
            "[ticket.cs_review] success ticket_id={} from_status={} to_status={} reviewer_id={}",
            ticket.id,
            old_status,
            ticket.status,
            reviewer_id,
        )
        return ticket

    async def assign_tech(
        self,
        *,
        ticket_id: int,
        operator_id: int,
        tech_id: int,
        comment: str | None,
    ) -> Ticket:
        logger.info(
            "[ticket.assign_tech] start ticket_id={} operator_id={} tech_id={} comment={}",
            ticket_id,
            operator_id,
            tech_id,
            comment,
        )
        ticket = await self.get_ticket(ticket_id)
        if ticket.status not in {TicketStatus.TECH_PROCESSING, TicketStatus.FIELD_VERIFICATION}:
            raise HTTPException(status_code=400, detail="仅技术处理中工单支持变更技术处理人")

        tech_user = await User.filter(id=tech_id, is_active=True, roles__name="技术").first()
        if not tech_user:
            raise HTTPException(status_code=400, detail="请选择有效的技术处理人")
        if ticket.tech_id == tech_id:
            raise HTTPException(status_code=400, detail="新的技术处理人与当前处理人相同")

        old_status = ticket.status
        old_tech_id = ticket.tech_id
        comment = self._sanitize_rich_html(comment) or f"技术处理人由 {old_tech_id or '-'} 变更为 {tech_id}"
        ticket.tech_id = tech_id
        await ticket.save()

        await self._write_action(
            ticket_id=ticket.id,
            action=TicketActionType.TECH_ASSIGN,
            from_status=old_status,
            to_status=ticket.status,
            operator_id=operator_id,
            comment=comment,
        )
        await self._notify_ticket_status_if_needed(ticket=ticket, operator_id=operator_id)
        logger.info(
            "[ticket.assign_tech] success ticket_id={} old_tech_id={} new_tech_id={} operator_id={}",
            ticket.id,
            old_tech_id,
            tech_id,
            operator_id,
        )
        return ticket

    async def set_tech_action(
        self,
        *,
        ticket_id: int,
        tech_id: int,
        action: TicketActionType,
        comment: str | None,
        root_cause: str | None,
    ) -> Ticket:
        logger.info(
            "[ticket.tech_action] start ticket_id={} tech_id={} action={} comment={}",
            ticket_id,
            tech_id,
            action,
            comment,
        )
        comment = self._sanitize_rich_html(comment)
        ticket = await self.get_ticket(ticket_id)
        if ticket.status not in {TicketStatus.TECH_PROCESSING, TicketStatus.FIELD_VERIFICATION}:
            raise HTTPException(status_code=400, detail="当前状态不可进行技术处理")

        if action not in {
            TicketActionType.TECH_START,
            TicketActionType.TECH_NOTE,
            TicketActionType.FIELD_VERIFY,
            TicketActionType.FIELD_REJECT,
            TicketActionType.TECH_REJECT,
            TicketActionType.FINISH,
        }:
            raise HTTPException(status_code=400, detail="不支持的技术操作")

        if action in {TicketActionType.FINISH, TicketActionType.FIELD_VERIFY}:
            setting = await system_setting_controller.get_public_config()
            root_causes = setting.get("ticket_root_causes") or []
            normalized_root_cause = (root_cause or "").strip()
            if not normalized_root_cause:
                raise HTTPException(status_code=400, detail="处理完成或转现场验证时必须选择问题根因")
            if root_causes and normalized_root_cause not in root_causes:
                raise HTTPException(status_code=400, detail="问题根因不合法，请刷新页面后重试")
        else:
            normalized_root_cause = None

        old_status = ticket.status
        if action == TicketActionType.TECH_REJECT:
            ticket.status = TicketStatus.TECH_REJECTED
            ticket.reject_reason = comment or "技术驳回"
        elif action == TicketActionType.FINISH:
            ticket.status = TicketStatus.PENDING_CLOSE
            ticket.reject_reason = None
            ticket.root_cause = normalized_root_cause
        elif action == TicketActionType.TECH_START:
            ticket.status = TicketStatus.TECH_PROCESSING
            ticket.reject_reason = None
        elif action == TicketActionType.TECH_NOTE:
            ticket.status = old_status
        elif action == TicketActionType.FIELD_VERIFY:
            ticket.status = TicketStatus.FIELD_VERIFICATION
            ticket.reject_reason = None
            ticket.root_cause = normalized_root_cause
        elif action == TicketActionType.FIELD_REJECT:
            ticket.status = TicketStatus.TECH_PROCESSING
            ticket.reject_reason = None

        ticket.tech_id = tech_id
        await ticket.save()

        await self._write_action(
            ticket_id=ticket.id,
            action=action,
            from_status=old_status,
            to_status=ticket.status,
            operator_id=tech_id,
            comment=comment,
        )
        await self._notify_ticket_status_if_needed(ticket=ticket, operator_id=tech_id)
        logger.info(
            "[ticket.tech_action] success ticket_id={} from_status={} to_status={} tech_id={}",
            ticket.id,
            old_status,
            ticket.status,
            tech_id,
        )
        return ticket

    async def update_ticket(
        self,
        *,
        ticket_id: int,
        operator_id: int,
        role_names: list[str],
        payload: dict,
        attachment_ids: list[int],
    ) -> Ticket:
        ticket = await self.get_ticket(ticket_id)
        can_edit = (
            ticket.submitter_id == operator_id
            or "客服" in role_names
            or "管理员" in role_names
            or (ticket.tech_id == operator_id and "技术" in role_names)
        )
        if not can_edit:
            raise HTTPException(status_code=403, detail="无权编辑该工单")
        if ticket.status == TicketStatus.DONE:
            raise HTTPException(status_code=400, detail="已关闭工单不可编辑")

        old_status = ticket.status
        old_status_value = str(old_status)
        if "description" in payload:
            payload["description"] = self._sanitize_rich_html(payload.get("description"))
        for k, v in payload.items():
            setattr(ticket, k, v)

        ticket.reject_reason = None
        if old_status_value == TicketStatus.TECH_REJECTED.value:
            ticket.status = TicketStatus.TECH_PROCESSING
            action = TicketActionType.TECH_START
            action_comment = "编辑后重新流转技术处理"
        elif old_status_value == TicketStatus.CS_REJECTED.value:
            config = await system_setting_controller.get_public_config()
            if self._needs_customer_service_review(ticket.project_phase, config):
                ticket.status = TicketStatus.PENDING_REVIEW
                action = TicketActionType.RESUBMIT
                action_comment = "编辑后重新提交客服审核"
            else:
                tech_user = await self._get_first_active_tech_user()
                if tech_user:
                    ticket.status = TicketStatus.TECH_PROCESSING
                    ticket.tech_id = tech_user.id
                    action = TicketActionType.TECH_START
                    action_comment = "编辑后无需客服审核，重新流转技术处理"
                else:
                    logger.warning("[ticket.update] skip_cs_review_failed ticket_id={} reason=no_active_tech_user", ticket.id)
                    ticket.status = TicketStatus.PENDING_REVIEW
                    action = TicketActionType.RESUBMIT
                    action_comment = "编辑后重新提交客服审核"
        else:
            ticket.status = old_status
            action = TicketActionType.RESUBMIT
            action_comment = "编辑工单"

        await ticket.save()
        await ticket.refresh_from_db()

        if attachment_ids:
            await self._bind_attachments(
                ticket_id=ticket.id,
                attachment_ids=attachment_ids,
                owner_ids=[operator_id, ticket.submitter_id],
            )

        await self._write_action(
            ticket_id=ticket.id,
            action=action,
            from_status=old_status,
            to_status=ticket.status,
            operator_id=operator_id,
            comment=action_comment,
        )
        await self._notify_ticket_status_if_needed(ticket=ticket, operator_id=operator_id)
        return ticket

    async def close_ticket(self, *, ticket_id: int, operator_id: int, role_names: list[str], comment: str | None) -> Ticket:
        ticket = await self.get_ticket(ticket_id)
        is_tech = ticket.tech_id == operator_id and "技术" in role_names
        is_submitter = ticket.submitter_id == operator_id
        is_admin = "管理员" in role_names
        if not (is_tech or is_submitter or is_admin):
            raise HTTPException(status_code=403, detail="仅提交者、当前技术或管理员可关闭工单")
        if ticket.status != TicketStatus.PENDING_CLOSE:
            raise HTTPException(status_code=400, detail="仅待关闭工单可关闭")

        old_status = ticket.status
        ticket.status = TicketStatus.DONE
        ticket.reject_reason = None
        ticket.finished_at = datetime.now()
        await ticket.save()

        await self._write_action(
            ticket_id=ticket.id,
            action=TicketActionType.CLOSE,
            from_status=old_status,
            to_status=ticket.status,
            operator_id=operator_id,
            comment=self._sanitize_rich_html(comment) or ("技术处理完成，关闭" if is_tech else "关闭工单"),
        )
        await self._notify_ticket_status_if_needed(ticket=ticket, operator_id=operator_id)
        return ticket

    async def set_field_verification_result(
        self,
        *,
        ticket_id: int,
        operator_id: int,
        approved: bool,
        comment: str | None,
    ) -> Ticket:
        ticket = await self.get_ticket(ticket_id)
        if ticket.submitter_id != operator_id:
            raise HTTPException(status_code=403, detail="仅提交者可处理现场验证结果")
        if ticket.status != TicketStatus.FIELD_VERIFICATION:
            raise HTTPException(status_code=400, detail="仅现场验证中的工单可处理验证结果")

        old_status = ticket.status
        sanitized_comment = self._sanitize_rich_html(comment)
        if approved:
            ticket.status = TicketStatus.DONE
            ticket.reject_reason = None
            ticket.finished_at = datetime.now()
            action = TicketActionType.CLOSE
            action_comment = sanitized_comment or "关闭工单"
        else:
            ticket.status = TicketStatus.TECH_PROCESSING
            ticket.reject_reason = sanitized_comment or "现场验证不通过"
            action = TicketActionType.FIELD_REJECT
            action_comment = ticket.reject_reason

        await ticket.save()
        await self._write_action(
            ticket_id=ticket.id,
            action=action,
            from_status=old_status,
            to_status=ticket.status,
            operator_id=operator_id,
            comment=action_comment,
        )
        await self._notify_ticket_status_if_needed(ticket=ticket, operator_id=operator_id)
        return ticket

    async def resubmit_ticket(
        self, *, ticket_id: int, submitter_id: int, description: str | None, attachment_ids: list[int]
    ) -> Ticket:
        logger.info(
            "[ticket.resubmit] start ticket_id={} submitter_id={} attachment_count={} has_description={}",
            ticket_id,
            submitter_id,
            len(attachment_ids),
            bool(description),
        )
        ticket = await self.get_ticket(ticket_id)
        if ticket.submitter_id != submitter_id:
            raise HTTPException(status_code=403, detail="只能由提交人重提工单")
        if ticket.status not in {TicketStatus.CS_REJECTED, TicketStatus.TECH_REJECTED}:
            raise HTTPException(status_code=400, detail="当前状态不可重提")

        old_status = ticket.status
        if description:
            ticket.description = self._sanitize_rich_html(description)
        ticket.reject_reason = None
        action = TicketActionType.RESUBMIT
        action_comment = "重提工单"
        if old_status == TicketStatus.TECH_REJECTED:
            ticket.status = TicketStatus.TECH_PROCESSING
            action = TicketActionType.TECH_START
        else:
            config = await system_setting_controller.get_public_config()
            if self._needs_customer_service_review(ticket.project_phase, config):
                ticket.status = TicketStatus.PENDING_REVIEW
            else:
                tech_user = await self._get_first_active_tech_user()
                if tech_user:
                    ticket.status = TicketStatus.TECH_PROCESSING
                    ticket.tech_id = tech_user.id
                    action = TicketActionType.TECH_START
                    action_comment = "重提后无需客服审核，自动进入技术处理"
                else:
                    logger.warning("[ticket.resubmit] skip_cs_review_failed ticket_id={} reason=no_active_tech_user", ticket.id)
                    ticket.status = TicketStatus.PENDING_REVIEW
        await ticket.save()

        if attachment_ids:
            await self._bind_attachments(ticket_id=ticket.id, attachment_ids=attachment_ids, owner_ids=[submitter_id, ticket.submitter_id])

        await self._write_action(
            ticket_id=ticket.id,
            action=action,
            from_status=old_status,
            to_status=ticket.status,
            operator_id=submitter_id,
            comment=action_comment,
        )
        await self._notify_ticket_status_if_needed(ticket=ticket, operator_id=submitter_id)
        logger.info(
            "[ticket.resubmit] success ticket_id={} from_status={} to_status={} submitter_id={}",
            ticket.id,
            old_status,
            ticket.status,
            submitter_id,
        )
        return ticket

    async def upload_attachment(self, *, uploader_id: int, file: UploadFile) -> TicketAttachment:
        logger.info("[ticket.upload] start uploader_id={} filename={} content_type={}", uploader_id, file.filename, file.content_type)
        filename = (file.filename or "").strip()
        if not filename:
            raise HTTPException(status_code=400, detail="文件名不能为空")

        ext = normalize_ext(filename)
        config = await system_setting_controller.get_public_config()
        allowed_extensions = self._normalize_extensions(config.get("ticket_attachment_extensions"))
        if not allowed_extensions:
            allowed_extensions = self._normalize_extensions([item.lstrip(".") for item in settings.ALLOWED_EXTENSIONS])
        if ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件后缀，仅允许：{', '.join(allowed_extensions)}（系统会按文件magic头校验真实类型）",
            )

        now = datetime.now()
        rel_dir = os.path.join("tickets", now.strftime("%Y"), now.strftime("%m"), now.strftime("%d"))
        abs_dir = os.path.join(settings.UPLOAD_DIR, rel_dir)
        os.makedirs(abs_dir, exist_ok=True)

        stored_name = f"{uuid.uuid4().hex}.{ext}"
        rel_path = os.path.join(rel_dir, stored_name).replace("\\", "/")
        abs_path = os.path.join(settings.UPLOAD_DIR, rel_path)

        total_size = 0
        head = b""
        chunk_size = 1024 * 1024
        try:
            with open(abs_path, "wb") as f:
                while True:
                    chunk = await file.read(chunk_size)
                    if not chunk:
                        break
                    if len(head) < 64:
                        head += chunk[: 64 - len(head)]
                    total_size += len(chunk)
                    if total_size > settings.MAX_UPLOAD_SIZE:
                        raise HTTPException(status_code=400, detail="文件大小超限")
                    f.write(chunk)
        except HTTPException:
            try:
                os.remove(abs_path)
            except OSError:
                pass
            raise
        except OSError as exc:
            try:
                os.remove(abs_path)
            except OSError:
                pass
            raise HTTPException(status_code=500, detail=f"保存文件失败: {exc}")

        detected_ext = detect_file_type(head, filename, abs_path)
        if not detected_ext:
            raise HTTPException(status_code=400, detail="无法识别文件magic头，请上传受支持的标准文件")
        if detected_ext != ext:
            try:
                os.remove(abs_path)
            except OSError:
                pass
            raise HTTPException(status_code=400, detail=f"文件magic头与扩展名不匹配，检测到真实类型为 {detected_ext}")
        if detected_ext not in allowed_extensions:
            try:
                os.remove(abs_path)
            except OSError:
                pass
            raise HTTPException(status_code=400, detail=f"检测到的真实类型 {detected_ext} 未被允许上传（按magic头校验）")

        attachment = await TicketAttachment.create(
            ticket_id=None,
            origin_name=filename,
            file_path=rel_path,
            file_size=total_size,
            mime_type=guess_type(filename)[0] or file.content_type or "application/octet-stream",
            uploader_id=uploader_id,
        )
        logger.info(
            "[ticket.upload] success attachment_id={} uploader_id={} size={} path={}",
            attachment.id,
            uploader_id,
            attachment.file_size,
            attachment.file_path,
        )
        return attachment

    async def get_ticket_detail(self, ticket_id: int, ticket: Ticket | None = None) -> dict:
        if ticket is None:
            ticket = await self.get_ticket(ticket_id)
        attachment_rows, action_rows = await asyncio.gather(
            TicketAttachment.filter(ticket_id=ticket_id).order_by("id"),
            TicketActionLog.filter(ticket_id=ticket_id).order_by("id"),
        )

        attachment_data, action_data = await asyncio.gather(
            asyncio.gather(*(item.to_dict() for item in attachment_rows)),
            asyncio.gather(*(item.to_dict() for item in action_rows)),
        )

        user_ids = {
            ticket.submitter_id,
            *(uid for uid in [ticket.reviewer_id, ticket.tech_id] if uid),
            *(item.operator_id for item in action_rows if item.operator_id),
        }
        user_map: dict[int, str] = {}
        if user_ids:
            for uid in list(user_ids):
                try:
                    basic = await user_controller.get_user_basic(int(uid))
                    user_map[int(uid)] = str(basic.get("alias") or basic.get("username") or "")
                except Exception:
                    user_map[int(uid)] = ""

        for item in action_data:
            item["operator_name"] = user_map.get(item.get("operator_id"), "")
            if not item["operator_name"]:
                op_id = item.get("operator_id")
                if op_id == ticket.reviewer_id:
                    item["operator_name"] = user_map.get(ticket.reviewer_id or 0, "")
                elif op_id == ticket.tech_id:
                    item["operator_name"] = user_map.get(ticket.tech_id or 0, "")
                elif op_id == ticket.submitter_id:
                    item["operator_name"] = user_map.get(ticket.submitter_id, "")
            item["operator_display"] = item.get("operator_name") or item.get("operator_id") or "-"

        data = await ticket.to_dict()
        data["attachments"] = list(attachment_data)
        data["attachment_count"] = len(attachment_data)
        data["actions"] = list(action_data)
        data["submitter_name"] = user_map.get(ticket.submitter_id, "")
        data["reviewer_name"] = user_map.get(ticket.reviewer_id or 0, "")
        data["tech_name"] = user_map.get(ticket.tech_id or 0, "")
        logger.info(
            "[ticket.detail] ticket_id={} attachment_count={} attachment_ids={}",
            ticket_id,
            data["attachment_count"],
            [item.get("id") for item in data["attachments"]],
        )
        return data

    async def get_attachment_download(self, *, attachment_id: int, user: User, role_names: list[str]) -> dict:
        attachment = await TicketAttachment.filter(id=attachment_id).first()
        if not attachment:
            raise HTTPException(status_code=404, detail="附件不存在")
        if not attachment.ticket_id:
            raise HTTPException(status_code=400, detail="附件尚未绑定工单")

        ticket = await Ticket.filter(id=attachment.ticket_id).first()
        if not ticket:
            raise HTTPException(status_code=404, detail="所属工单不存在")

        if not user.is_superuser and user.username != "admin" and not {"管理员", "客服"}.intersection(role_names):
            if "技术" in role_names:
                related_submitter_ids = await self._tech_related_submitter_ids(user.id)
                if ticket.submitter_id != user.id and ticket.tech_id != user.id and ticket.submitter_id not in related_submitter_ids:
                    raise HTTPException(status_code=403, detail="无权限下载该附件")
            elif ticket.submitter_id != user.id:
                raise HTTPException(status_code=403, detail="无权限下载该附件")

        abs_path = os.path.normcase(os.path.realpath(os.path.join(settings.UPLOAD_DIR, attachment.file_path)))
        upload_root = os.path.normcase(os.path.realpath(settings.UPLOAD_DIR))
        try:
            in_root = os.path.commonpath([abs_path, upload_root]) == upload_root
        except ValueError:
            in_root = False
        if not in_root:
            raise HTTPException(status_code=400, detail="附件路径非法")
        if not os.path.exists(abs_path):
            raise HTTPException(status_code=404, detail="附件文件不存在")

        return {
            "abs_path": abs_path,
            "filename": attachment.origin_name or os.path.basename(attachment.file_path),
            "media_type": attachment.mime_type or "application/octet-stream",
            "headers": {"Content-Disposition": build_download_content_disposition(attachment.origin_name or "download")},
        }

    async def cache_attachment_preview(self, *, attachment_id: int, user: User, role_names: list[str]) -> dict:
        data = await self.get_attachment_download(attachment_id=attachment_id, user=user, role_names=role_names)
        abs_path = data["abs_path"]
        stat = os.stat(abs_path)
        cache_key = hashlib.sha256(f"ticket:{abs_path}:{stat.st_mtime_ns}:{stat.st_size}".encode("utf-8")).hexdigest()[:24]
        filename = webdav_controller._safe_preview_filename(data["filename"])
        target_dir = os.path.join(webdav_controller.PREVIEW_CACHE_DIR, cache_key)
        target_path = os.path.join(target_dir, filename)

        if not os.path.exists(target_path) or os.path.getsize(target_path) <= 0:
            os.makedirs(target_dir, exist_ok=True)
            temp_path = f"{target_path}.tmp"
            try:
                shutil.copyfile(abs_path, temp_path)
                os.replace(temp_path, target_path)
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)

        return {
            "preview_url": await webdav_controller._build_preview_cache_url(cache_key, filename),
            "content_type": data["media_type"],
        }


ticket_controller = TicketController()
