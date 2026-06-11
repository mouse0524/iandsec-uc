from datetime import datetime
from html.parser import HTMLParser
import json

from fastapi import HTTPException

from app.controllers.mail import mail_controller
from app.core.redis_client import execute_redis
from app.models.admin import GlobalNotice, GlobalNoticeUser, Role, User
from app.settings import settings
from app.controllers.user import user_controller


class _PlainTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data:
            self.parts.append(data)


class NoticeController:
    INBOX_CACHE_TTL_SECONDS = 300
    UNREAD_CACHE_TTL_SECONDS = 300

    @staticmethod
    def _fmt_dt(value):
        if isinstance(value, datetime):
            return value.strftime(settings.DATETIME_FORMAT)
        return value

    @staticmethod
    def _inbox_cache_key(user_id: int) -> str:
        return f"notice:inbox10:user:{user_id}"

    @staticmethod
    def _unread_cache_key(user_id: int) -> str:
        return f"notice:unread:user:{user_id}"

    async def _clear_inbox_cache(self, user_id: int) -> None:
        try:
            await execute_redis("delete", self._inbox_cache_key(user_id))
        except Exception:
            pass

    async def _clear_unread_cache(self, user_id: int) -> None:
        try:
            await execute_redis("delete", self._unread_cache_key(user_id))
        except Exception:
            pass

    @staticmethod
    def _plain_text_length(html: str) -> int:
        parser = _PlainTextExtractor()
        parser.feed(str(html or ""))
        parser.close()
        return len("".join(parser.parts).strip())

    @staticmethod
    async def _get_cached_unread(user_id: int) -> int | None:
        try:
            raw = await execute_redis("get", NoticeController._unread_cache_key(user_id))
            if raw is None:
                return None
            return int(raw)
        except Exception:
            return None

    @staticmethod
    async def _set_cached_unread(user_id: int, value: int) -> None:
        try:
            await execute_redis(
                "setex",
                NoticeController._unread_cache_key(user_id),
                NoticeController.UNREAD_CACHE_TTL_SECONDS,
                str(max(0, int(value))),
            )
        except Exception:
            pass

    async def _resolve_target_user_ids(self, *, target_type: str, target_role_ids: list[int], target_user_ids: list[int]) -> list[int]:
        if target_type == "all":
            return await User.filter(is_active=True).values_list("id", flat=True)
        if target_type == "roles":
            if not target_role_ids:
                raise HTTPException(status_code=400, detail="请选择目标角色")
            role_ids = [int(item) for item in target_role_ids if item]
            if not role_ids:
                raise HTTPException(status_code=400, detail="请选择目标角色")
            users = await User.filter(is_active=True, roles__id__in=role_ids).distinct().values_list("id", flat=True)
            return list(users)
        if target_type == "users":
            if not target_user_ids:
                raise HTTPException(status_code=400, detail="请选择目标用户")
            user_ids = [int(item) for item in target_user_ids if item]
            if not user_ids:
                raise HTTPException(status_code=400, detail="请选择目标用户")
            valid_users = await User.filter(is_active=True, id__in=user_ids).values_list("id", flat=True)
            return list(valid_users)
        raise HTTPException(status_code=400, detail="不支持的发送范围")

    @staticmethod
    def _normalize_delivery_channels(value) -> list[str]:
        source = ["site"] if value is None else value
        channels = [str(item or "").strip() for item in source]
        channels = [item for item in channels if item in {"site", "email"}]
        return list(dict.fromkeys(channels))

    async def create_notice(self, *, creator_id: int, payload: dict) -> tuple[GlobalNotice, dict]:
        content_html = str(payload.get("content_html") or "").strip()
        if not content_html:
            raise HTTPException(status_code=400, detail="通知内容不能为空")
        if self._plain_text_length(content_html) > 2000:
            raise HTTPException(status_code=400, detail="通知内容纯文本长度不能超过2000")

        delivery_channels = self._normalize_delivery_channels(payload.get("delivery_channels"))
        if not delivery_channels:
            raise HTTPException(status_code=400, detail="请至少选择一种通知方式")

        target_type = payload.get("target_type")
        role_ids = payload.get("target_role_ids") or []
        user_ids = payload.get("target_user_ids") or []
        recipients = await self._resolve_target_user_ids(
            target_type=target_type,
            target_role_ids=role_ids,
            target_user_ids=user_ids,
        )
        if not recipients:
            raise HTTPException(status_code=400, detail="未匹配到可接收通知的用户")

        notice = await GlobalNotice.create(
            title=(payload.get("title") or "").strip() or None,
            content_html=content_html,
            target_type=target_type,
            target_role_ids=[int(item) for item in role_ids if item],
            target_user_ids=[int(item) for item in user_ids if item],
            delivery_channels=delivery_channels,
            created_by=creator_id,
            is_active=True,
        )

        unique_recipients = sorted(set(recipients))
        site_count = 0
        if "site" in delivery_channels:
            rows = [GlobalNoticeUser(notice_id=notice.id, user_id=uid, is_read=False) for uid in unique_recipients]
            await GlobalNoticeUser.bulk_create(rows)
            site_count = len(rows)
            for uid in unique_recipients:
                await self._clear_inbox_cache(uid)
                cached_unread = await self._get_cached_unread(uid)
                if cached_unread is None:
                    await self._clear_unread_cache(uid)
                else:
                    await self._set_cached_unread(uid, cached_unread + 1)

        email_count = 0
        if "email" in delivery_channels:
            users = await User.filter(is_active=True, id__in=unique_recipients).all()
            email_count = await mail_controller.send_global_notice(
                to_users=users,
                title=notice.title,
                content_html=content_html,
            )

        return notice, {
            "recipient_count": len(unique_recipients),
            "site_recipient_count": site_count,
            "email_recipient_count": email_count,
        }

    async def list_notice(self, *, page: int, page_size: int) -> tuple[int, list[dict]]:
        query = GlobalNotice.filter(is_active=True)
        total = await query.count()
        rows = await query.order_by("-id").offset((page - 1) * page_size).limit(page_size).values()
        if not rows:
            return total, []

        creator_ids = [item["created_by"] for item in rows if item.get("created_by")]
        creator_map: dict[int, str] = {}
        for creator_id in set(creator_ids):
            try:
                user_basic = await user_controller.get_user_basic(int(creator_id))
                creator_map[int(creator_id)] = str(user_basic.get("alias") or user_basic.get("username") or "")
            except Exception:
                creator_map[int(creator_id)] = ""

        all_role_ids = {rid for item in rows for rid in (item.get("target_role_ids") or [])}
        role_map: dict[int, str] = {}
        if all_role_ids:
            roles = await Role.filter(id__in=list(all_role_ids)).values("id", "name")
            role_map = {r["id"]: r["name"] for r in roles}

        for row in rows:
            row["creator_name"] = creator_map.get(row.get("created_by"), "")
            row["target_role_names"] = [role_map.get(int(rid), str(rid)) for rid in (row.get("target_role_ids") or [])]
            row["delivery_channels"] = self._normalize_delivery_channels(row.get("delivery_channels"))
            row["created_at"] = self._fmt_dt(row.get("created_at"))
            row["updated_at"] = self._fmt_dt(row.get("updated_at"))
        return total, rows

    async def inbox(self, *, user_id: int, page: int, page_size: int) -> tuple[int, list[dict]]:
        use_cache = page == 1 and page_size == 10
        if use_cache:
            try:
                raw = await execute_redis("get", self._inbox_cache_key(user_id))
                if raw:
                    cache_data = json.loads(raw)
                    return int(cache_data.get("total", 0)), list(cache_data.get("rows") or [])
            except Exception:
                pass

        query = GlobalNoticeUser.filter(user_id=user_id)
        total = await query.count()
        rows = await query.order_by("-id").offset((page - 1) * page_size).limit(page_size).values(
            "notice_id", "is_read", "read_at", "delivered_at"
        )
        if not rows:
            return total, []

        notice_ids = [item["notice_id"] for item in rows]
        notices = await GlobalNotice.filter(id__in=notice_ids, is_active=True).values("id", "title", "content_html", "created_at")
        notice_map = {item["id"]: item for item in notices}

        result: list[dict] = []
        for row in rows:
            notice = notice_map.get(row["notice_id"])
            if not notice:
                continue
            result.append(
                {
                    "notice_id": row["notice_id"],
                    "title": notice.get("title"),
                    "content_html": notice.get("content_html") or "",
                    "is_read": row.get("is_read", False),
                    "read_at": self._fmt_dt(row.get("read_at")),
                    "delivered_at": self._fmt_dt(row.get("delivered_at")),
                    "created_at": self._fmt_dt(notice.get("created_at")),
                }
            )

        if use_cache:
            try:
                payload = json.dumps({"total": total, "rows": result}, ensure_ascii=False)
                await execute_redis("setex", self._inbox_cache_key(user_id), self.INBOX_CACHE_TTL_SECONDS, payload)
            except Exception:
                pass
        return total, result

    async def unread_count(self, *, user_id: int) -> int:
        cached = await self._get_cached_unread(user_id)
        if cached is not None:
            return cached

        count = await GlobalNoticeUser.filter(user_id=user_id, is_read=False).count()
        await self._set_cached_unread(user_id, count)
        return count

    async def read_one(self, *, user_id: int, notice_id: int) -> bool:
        obj = await GlobalNoticeUser.filter(user_id=user_id, notice_id=notice_id).first()
        if not obj:
            return False
        if not obj.is_read:
            obj.is_read = True
            obj.read_at = datetime.now()
            await obj.save()
            await self._clear_inbox_cache(user_id)
            cached_unread = await self._get_cached_unread(user_id)
            if cached_unread is None:
                await self._clear_unread_cache(user_id)
            else:
                await self._set_cached_unread(user_id, cached_unread - 1)
        return True

    async def read_all(self, *, user_id: int) -> int:
        rows = await GlobalNoticeUser.filter(user_id=user_id, is_read=False).all()
        if not rows:
            return 0
        now = datetime.now()
        for item in rows:
            item.is_read = True
            item.read_at = now
        await GlobalNoticeUser.bulk_update(rows, fields=["is_read", "read_at"])
        await self._clear_inbox_cache(user_id)
        await self._set_cached_unread(user_id, 0)
        return len(rows)


notice_controller = NoticeController()
