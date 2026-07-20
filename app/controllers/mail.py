import asyncio
import re
import secrets
import smtplib
import time
from email.mime.text import MIMEText
from email.utils import formataddr

from fastapi import HTTPException
from email_validator import EmailNotValidError, validate_email

from app.controllers.system_setting import system_setting_controller
from app.core.redis_client import execute_redis
from app.log import logger
from app.models.admin import Ticket, User
from app.models.enums import TicketStatus
from app.settings import settings


_LOCAL_EMAIL_CODE_CACHE: dict[str, dict] = {}


class MailController:
    @staticmethod
    def _gen_code(length: int = 6) -> str:
        return "".join(secrets.choice("0123456789") for _ in range(length))

    @staticmethod
    def _sanitize_header(value) -> str:
        return str(value or "").replace("\r", "").replace("\n", "").strip()

    @staticmethod
    async def _get_setting() -> dict:
        return await system_setting_controller.get_full_dict()

    @staticmethod
    def _render_template(template: str, params: dict) -> str:
        content = template or ""
        for key, value in params.items():
            content = content.replace("{" + key + "}", str(value if value is not None else ""))
        return content

    @staticmethod
    def _ticket_url(ticket: Ticket, setting: dict) -> str:
        base_url = str(setting.get("site_base_url") or settings.APP_PUBLIC_BASE_URL or "").strip().rstrip("/")
        path = f"/issue/detail/issue_id/{getattr(ticket, 'id', '')}"
        return f"{base_url}{path}" if base_url else path

    @staticmethod
    def _ticket_link(ticket_url: str) -> str:
        return (
            f'<a href="{ticket_url}" style="display:inline-block;padding:8px 12px;'
            f'border-radius:6px;background:#2563eb;color:#fff;text-decoration:none;" '
            f'target="_blank" rel="noopener noreferrer">查看工单</a>'
        )

    @staticmethod
    def _ensure_ticket_link_href(content: str, ticket_url: str) -> str:
        return re.sub(
            r"<a\b[^>]*>\s*查看工单\s*</a>",
            MailController._ticket_link(ticket_url),
            content,
            flags=re.IGNORECASE,
        )

    @staticmethod
    def _register_type_label(register_type: str) -> str:
        return "渠道商" if register_type == "channel" else "用户"

    @staticmethod
    def _is_valid_email(to_email: str) -> bool:
        try:
            validate_email(str(to_email or "").strip(), check_deliverability=False)
            return True
        except EmailNotValidError:
            return False

    @staticmethod
    def _schedule(coro, *, tag: str) -> None:
        task = asyncio.create_task(coro)

        def _done_callback(done_task: asyncio.Task) -> None:
            try:
                done_task.result()
            except Exception as exc:
                logger.warning("[mail.task] async_send_failed tag={} error={}", tag, str(exc))

        task.add_done_callback(_done_callback)

    async def _send_email(self, *, to_email: str, subject: str, content: str, is_html: bool = False) -> None:
        to_email = self._sanitize_header(to_email)
        if not self._is_valid_email(to_email):
            logger.warning("[mail.send] invalid_email skip to_email={} subject={}", to_email, subject)
            return

        setting = await self._get_setting()
        if not setting.get("smtp_host") or not setting.get("smtp_sender"):
            raise HTTPException(status_code=400, detail="系统未配置发件箱")

        msg = MIMEText(content, "html" if is_html else "plain", "utf-8")
        from_email = self._sanitize_header(setting.get("smtp_sender"))
        from_name = self._sanitize_header(setting.get("smtp_sender_name") or "系统通知")
        msg["From"] = formataddr((from_name, from_email))
        msg["To"] = to_email
        msg["Subject"] = self._sanitize_header(subject)

        username = setting.get("smtp_username") or from_email
        try:
            if setting.get("smtp_use_ssl"):
                with smtplib.SMTP_SSL(setting.get("smtp_host"), int(setting.get("smtp_port") or 465), timeout=10) as server:
                    if username and setting.get("smtp_password"):
                        server.login(username, setting.get("smtp_password"))
                    server.sendmail(from_email, [to_email], msg.as_string())
            else:
                with smtplib.SMTP(setting.get("smtp_host"), int(setting.get("smtp_port") or 465), timeout=10) as server:
                    if setting.get("smtp_use_tls"):
                        server.starttls()
                    if username and setting.get("smtp_password"):
                        server.login(username, setting.get("smtp_password"))
                    server.sendmail(from_email, [to_email], msg.as_string())
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"发送邮件失败: {exc}")

    @staticmethod
    def _cleanup_local_cache() -> None:
        now = time.time()
        expired_keys = [k for k, v in _LOCAL_EMAIL_CODE_CACHE.items() if v.get("expires_at", 0) <= now]
        for key in expired_keys:
            _LOCAL_EMAIL_CODE_CACHE.pop(key, None)

    @staticmethod
    def _set_local_code(email: str, code: str) -> None:
        MailController._cleanup_local_cache()
        key = email.lower().strip()
        _LOCAL_EMAIL_CODE_CACHE[key] = {
            "code": code.strip(),
            "expires_at": time.time() + settings.EMAIL_VERIFY_TTL_SECONDS,
        }

    @staticmethod
    def _verify_local_code(email: str, code: str) -> bool:
        MailController._cleanup_local_cache()
        key = email.lower().strip()
        item = _LOCAL_EMAIL_CODE_CACHE.get(key)
        if not item:
            return False
        is_valid = item.get("code") == code.strip()
        if is_valid:
            _LOCAL_EMAIL_CODE_CACHE.pop(key, None)
        return is_valid

    @staticmethod
    def _normalize_code(code) -> str:
        if code is None:
            return ""
        if isinstance(code, bytes):
            code = code.decode("utf-8")
        return str(code).strip()

    async def send_partner_verify_code(self, email: str) -> None:
        setting = await self._get_setting()

        code = self._gen_code()
        minutes = max(settings.EMAIL_VERIFY_TTL_SECONDS // 60, 1)
        content = (setting.get("email_verify_template") or "您好，您的验证码是：{code}，{minutes}分钟内有效。").format(
            code=code,
            minutes=minutes,
        )
        subject = setting.get("email_verify_subject") or "代理商注册验证码"

        self._set_local_code(email, code)
        try:
            await execute_redis(
                "setex", f"email_verify:{email.lower().strip()}", settings.EMAIL_VERIFY_TTL_SECONDS, code
            )
        except Exception as exc:
            logger.warning("[mail.verify_code] cache_write_failed email={} error={}", email, str(exc))
        self._schedule(
            self._send_email(
                to_email=email,
                subject=subject,
                content=content,
                is_html=bool(setting.get("email_verify_is_html", False)),
            ),
            tag="partner_verify",
        )

    async def send_reset_password_code(self, email: str) -> None:
        setting = await self._get_setting()
        code = self._gen_code()
        minutes = max(settings.EMAIL_VERIFY_TTL_SECONDS // 60, 1)
        subject = setting.get("reset_password_subject") or "密码重置验证码"
        template = setting.get("reset_password_template") or "您好，您的密码重置验证码是：{code}，{minutes}分钟内有效。"
        content = self._render_template(template, {"code": code, "minutes": minutes})
        self._set_local_code(email, code)
        try:
            await execute_redis("setex", f"email_verify:{email.lower().strip()}", settings.EMAIL_VERIFY_TTL_SECONDS, code)
        except Exception as exc:
            logger.warning("[mail.reset_code] cache_write_failed email={} error={}", email, str(exc))
        self._schedule(
            self._send_email(
                to_email=email,
                subject=subject,
                content=content,
                is_html=bool(setting.get("reset_password_is_html", False)),
            ),
            tag="reset_pwd_code",
        )

    async def verify_email_code(self, email: str, code: str) -> bool:
        key = f"email_verify:{email.lower().strip()}"
        try:
            saved = await execute_redis("get", key)
            if not saved:
                return self._verify_local_code(email, code)
            if self._normalize_code(saved) == self._normalize_code(code):
                await execute_redis("delete", key)
                _LOCAL_EMAIL_CODE_CACHE.pop(email.lower().strip(), None)
                return True
            return False
        except Exception:
            return self._verify_local_code(email, code)

    async def send_register_review_notice(
        self,
        *,
        to_email: str,
        contact_name: str,
        register_type: str,
        approved: bool,
        reason: str | None = None,
    ) -> None:
        setting = await self._get_setting()
        register_type_text = self._register_type_label(register_type)

        if approved:
            subject = setting.get("register_review_approve_subject") or "注册审核结果通知"
            template = (
                setting.get("register_review_approve_template")
                or "您好，{contact_name}，您的{register_type}注册申请已审核通过，现可使用邮箱登录系统。"
            )
            is_html = bool(setting.get("register_review_approve_is_html", False))
        else:
            subject = setting.get("register_review_reject_subject") or "注册审核结果通知"
            template = (
                setting.get("register_review_reject_template")
                or "您好，{contact_name}，您的{register_type}注册申请已驳回。驳回理由：{reason}"
            )
            is_html = bool(setting.get("register_review_reject_is_html", False))

        content = self._render_template(
            template,
            {
                "contact_name": contact_name,
                "register_type": register_type_text,
                "reason": reason or "无",
            },
        )
        self._schedule(
            self._send_email(to_email=to_email, subject=subject, content=content, is_html=is_html),
            tag="register_review",
        )

    async def send_ticket_status_notice(
        self,
        *,
        ticket: Ticket,
        to_user: User,
        status: TicketStatus,
        operator_name: str,
    ) -> None:
        status_label_map = {
            TicketStatus.PENDING_REVIEW.value: "待客服审核",
            TicketStatus.CS_REJECTED.value: "驳回",
            TicketStatus.TECH_PROCESSING.value: "待技术处理",
            TicketStatus.TEST_FILTERING.value: "测试过滤",
            TicketStatus.PRODUCT_EVALUATION.value: "产品评估",
            TicketStatus.RD_PROCESSING.value: "研发处理",
            TicketStatus.TEST_VERIFICATION.value: "测试验证",
            TicketStatus.FIELD_VERIFICATION.value: "现场验证",
            TicketStatus.PENDING_CLOSE.value: "待关闭",
            TicketStatus.TECH_REJECTED.value: "驳回",
            TicketStatus.DONE.value: "已关闭",
        }
        setting = await self._get_setting()
        status_label = status_label_map.get(str(status), str(status))
        subject_template = setting.get("ticket_notify_subject") or "工单状态提醒：{ticket_no}"
        content_template = (
            setting.get("ticket_notify_template")
            or "您好，{name}：\n工单编号：{ticket_no}\n工单标题：{title}\n当前状态：{status}\n操作人：{operator}\n查看链接：{ticket_url}\n请及时登录系统处理。"
        )
        subject = self._render_template(subject_template, {"ticket_no": ticket.ticket_no})
        ticket_url = self._ticket_url(ticket, setting)
        ticket_link = self._ticket_link(ticket_url)
        content = self._render_template(
            content_template,
            {
                "name": to_user.alias or to_user.username,
                "ticket_no": ticket.ticket_no,
                "title": ticket.title,
                "status": status_label,
                "operator": operator_name or "-",
                "ticket_url": ticket_url,
                "ticket_link": ticket_link,
            },
        )
        is_html = bool(setting.get("ticket_notify_is_html", True))
        if "{ticket_url}" not in content_template and "{ticket_link}" not in content_template:
            content += (
                f'<p style="margin:10px 0 0;">{ticket_link}</p>'
                if is_html
                else f"\n查看链接：{ticket_url}"
            )
        if is_html:
            content = self._ensure_ticket_link_href(content, ticket_url)
        self._schedule(
            self._send_email(
                to_email=to_user.email,
                subject=subject,
                content=content,
                is_html=is_html,
            ),
            tag="ticket_notify",
        )

    async def send_global_notice(self, *, to_users: list[User], title: str | None, content_html: str) -> int:
        subject = (title or "").strip() or "系统通知"
        count = 0
        for user in to_users:
            if not user.email:
                continue
            count += 1
            self._schedule(
                self._send_email(
                    to_email=user.email,
                    subject=subject,
                    content=content_html,
                    is_html=True,
                ),
                tag="global_notice",
            )
        return count

    async def send_admin_reset_password_notice(self, *, to_user: User, temp_password: str) -> None:
        setting = await self._get_setting()
        subject = setting.get("admin_reset_password_subject") or "账号密码已重置"
        template = (
            setting.get("admin_reset_password_template")
            or "您好，{username}，管理员已重置您的账号密码。临时密码：{password}。请尽快登录后修改密码。"
        )
        content = self._render_template(
            template,
            {
                "username": to_user.alias or to_user.username,
                "password": temp_password,
                "email": to_user.email,
            },
        )
        self._schedule(
            self._send_email(
                to_email=to_user.email,
                subject=subject,
                content=content,
                is_html=bool(setting.get("admin_reset_password_is_html", True)),
            ),
            tag="admin_reset_pwd",
        )


mail_controller = MailController()
