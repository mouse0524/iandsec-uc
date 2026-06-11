import os
import uuid
from datetime import datetime
from urllib.parse import quote, urlparse
import json

import httpx
from fastapi import HTTPException, UploadFile
from tortoise.exceptions import IntegrityError

from app.log import logger
from app.core.redis_client import execute_redis
from app.models.admin import SystemSettingItem
from app.services.time_sync_service import time_sync_service
from app.settings import settings
from app.utils.file_signature import detect_file_type, normalize_ext


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def normalize_webdav_base_url(url: str | None) -> str:
    raw = str(url or "").strip().rstrip("/")
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise HTTPException(status_code=400, detail="WebDAV Base URL 地址必须使用 HTTP 或 HTTPS")
    if parsed.username or parsed.password:
        raise HTTPException(status_code=400, detail="WebDAV Base URL 地址不能包含认证信息")
    if parsed.query or parsed.fragment or "?" in raw or "#" in raw:
        raise HTTPException(status_code=400, detail="WebDAV Base URL 地址不能包含查询参数或片段")
    return raw


class SystemSettingController:
    PUBLIC_CONFIG_CACHE_KEY = "config:public:v1"
    REDMINE_METADATA_CACHE_KEY = "config:redmine:metadata:v1"
    PUBLIC_CONFIG_CACHE_TTL_SECONDS = 300
    REDMINE_METADATA_CACHE_TTL_SECONDS = 86400
    _SECTIONS = {
        "site",
        "ticket",
        "login_security",
        "time_sync",
        "ticket_notify",
        "mail",
        "mail_template",
        "webdav",
        "database_backup",
        "redmine",
    }

    _DEFAULTS = {
        "site": {
            "site_title": "安得和众用户服务中心",
            "site_logo": None,
            "allow_partner_register": True,
            "allow_channel_register": True,
            "allow_user_register": True,
            "customer_service_auto_approve_register": False,
        },
        "ticket": {
            "ticket_attachment_extensions": ["zip", "rar", "png", "jpg", "gif"],
            "ticket_project_phases": ["售前", "实施", "售后"],
            "ticket_cs_review_project_phases": ["实施", "售后"],
            "ticket_issue_types": ["现网问题", "现网需求", "产品建议"],
            "ticket_impact_scopes": ["全部", "偶现", "单台必现", "单台偶现"],
            "ticket_categories": ["登录问题", "权限问题", "系统异常", "其他"],
            "customer_service_auto_approve_ticket": False,
            "ticket_root_causes": ["代码缺陷", "配置错误", "环境异常", "数据问题", "操作不当", "第三方依赖"],
            "ticket_description_templates": [
                "问题现象：\n复现步骤：\n期望结果：\n实际结果：\n影响范围：",
                "发生时间：\n操作账号：\n所属模块：\n错误提示：\n已尝试方案：",
            ],
        },
        "login_security": {
            "login_security_enabled": True,
            "login_account_ip_fail_limit": 5,
            "login_account_ip_lock_minutes": 60,
            "login_ip_fail_limit": 20,
            "login_ip_lock_minutes": 60,
            "login_fail_window_minutes": 60,
            "login_generic_error_enabled": True,
            "user_token_expire_minutes": 60,
            "inactive_user_auto_disable_enabled": True,
            "inactive_user_auto_disable_days": 30,
            "password_min_length": 8,
            "password_required_categories": ["letter", "digit"],
        },
        "time_sync": {
            "time_sync_enabled": True,
            "time_sync_server": "ntp.aliyun.com",
            "time_sync_interval_minutes": 60,
            "time_sync_max_offset_seconds": 5,
            "time_sync_timezone": "Asia/Shanghai",
        },
        "ticket_notify": {
            "ticket_notify_by_role": {
                "用户": ["cs_rejected", "tech_rejected", "pending_close", "done"],
                "代理商": ["cs_rejected", "tech_rejected", "pending_close", "done"],
                "客服": ["pending_review"],
                "技术": ["tech_processing", "field_verification"],
            }
        },
        "mail": {
            "smtp_host": None,
            "smtp_port": 465,
            "smtp_username": None,
            "smtp_password": None,
            "smtp_sender": None,
            "smtp_sender_name": "系统通知",
            "smtp_use_tls": False,
            "smtp_use_ssl": True,
        },
        "mail_template": {
            "email_verify_subject": "代理商注册验证码",
            "email_verify_is_html": True,
            "email_verify_template": "您好，您的验证码是：{code}，{minutes}分钟内有效。",
            "register_review_approve_subject": "注册审核结果通知",
            "register_review_approve_is_html": True,
            "register_review_approve_template": "您好，{contact_name}，您的{register_type}注册申请已审核通过，现可使用邮箱登录系统。",
            "register_review_reject_subject": "注册审核结果通知",
            "register_review_reject_is_html": True,
            "register_review_reject_template": "您好，{contact_name}，您的{register_type}注册申请已驳回。驳回理由：{reason}",
            "reset_password_subject": "密码重置验证码",
            "reset_password_is_html": True,
            "reset_password_template": "<div style=\"font-family:Arial,'PingFang SC','Microsoft YaHei',sans-serif;color:#1f2937;line-height:1.7;background:#f8fbff;border:1px solid #dbeafe;border-radius:12px;padding:16px 18px;\"><h2 style=\"margin:0 0 12px;font-size:18px;color:#1d4ed8;\">找回密码验证码</h2><p style=\"margin:0 0 10px;\">您好，您正在进行密码重置操作，请使用以下验证码：</p><div style=\"display:inline-block;padding:10px 18px;border-radius:8px;background:#eff6ff;border:1px solid #bfdbfe;font-size:24px;font-weight:700;letter-spacing:4px;color:#1d4ed8;\">{code}</div><p style=\"margin:12px 0 0;color:#6b7280;\">验证码 {minutes} 分钟内有效，请勿泄露给他人。</p></div>",
            "admin_reset_password_subject": "账号密码已重置",
            "admin_reset_password_is_html": True,
            "admin_reset_password_template": "<div style=\"font-family:Arial,'PingFang SC','Microsoft YaHei',sans-serif;color:#1f2937;line-height:1.7;background:#fffaf0;border:1px solid #fde68a;border-radius:12px;padding:16px 18px;\"><h2 style=\"margin:0 0 12px;font-size:18px;color:#b45309;\">账号密码已重置</h2><p style=\"margin:0 0 8px;\">您好，<b>{username}</b>：</p><p style=\"margin:0 0 8px;\">管理员已重置您的账号密码，请使用以下临时密码登录：</p><div style=\"display:inline-block;padding:10px 14px;border-radius:8px;background:#fff7ed;border:1px solid #fed7aa;font-size:20px;font-weight:700;color:#c2410c;\">{password}</div><p style=\"margin:12px 0 0;color:#6b7280;\">登录后请尽快在个人中心修改密码。</p></div>",
            "ticket_notify_subject": "工单状态提醒：{ticket_no}",
            "ticket_notify_is_html": True,
            "ticket_notify_template": "<div style=\"font-family:Arial,'PingFang SC','Microsoft YaHei',sans-serif;color:#1f2937;line-height:1.7;background:#f8fbff;border:1px solid #dbeafe;border-radius:12px;padding:16px 18px;\"><h2 style=\"margin:0 0 12px;font-size:18px;color:#1d4ed8;\">工单状态提醒</h2><p style=\"margin:0 0 8px;\">您好，<b>{name}</b>：</p><p style=\"margin:0 0 6px;\">工单编号：<b>{ticket_no}</b></p><p style=\"margin:0 0 6px;\">工单标题：{title}</p><p style=\"margin:0 0 6px;\">当前状态：<b style=\"color:#1d4ed8;\">{status}</b></p><p style=\"margin:0 0 6px;\">操作人：{operator}</p><p style=\"margin:8px 0 0;color:#6b7280;\">请及时登录系统处理。</p></div>",
        },
        "webdav": {
            "webdav_enabled": False,
            "webdav_base_url": None,
            "webdav_username": None,
            "webdav_password": None,
            "webdav_share_default_expire_hours": 168,
            "webdav_signature_ttl": 24,
            "webdav_max_upload_size": 52428800,
            "webdav_signature_secret": None,
        },
        "database_backup": {
            "db_backup_enabled": False,
            "db_backup_directory": os.getenv(
                "DB_BACKUP_DIRECTORY",
                "/iandsec-db-backups",
            ),
            "db_backup_mysql_container": os.getenv("DB_BACKUP_MYSQL_CONTAINER", "iandsec-uc-mysql"),
            "db_backup_webdav_base_url": os.getenv("DB_BACKUP_WEBDAV_BASE_URL") or None,
            "db_backup_webdav_username": os.getenv("DB_BACKUP_WEBDAV_USERNAME") or None,
            "db_backup_webdav_password": os.getenv("DB_BACKUP_WEBDAV_PASSWORD") or None,
            "db_backup_run_at": os.getenv("DB_BACKUP_RUN_AT", "02:30"),
            "db_backup_retention_days": _int_env("DB_BACKUP_RETENTION_DAYS", 7),
        },
        "redmine": {
            "redmine_enabled": False,
            "redmine_base_url": os.getenv("REDMINE_BASE_URL") or None,
            "redmine_api_key": os.getenv("REDMINE_API_KEY") or None,
            "redmine_project_id": os.getenv("REDMINE_PROJECT_ID") or None,
            "redmine_tracker_id": _int_env("REDMINE_TRACKER_ID", 0) or None,
            "redmine_priority_id": _int_env("REDMINE_PRIORITY_ID", 0) or None,
            "redmine_assigned_to_id": _int_env("REDMINE_ASSIGNED_TO_ID", 0) or None,
            "redmine_project_phase_field_id": _int_env("REDMINE_PROJECT_PHASE_FIELD_ID", 0) or None,
            "redmine_os_field_id": _int_env("REDMINE_OS_FIELD_ID", 0) or None,
            "redmine_sync_visible_fields": [],
            "redmine_sync_options": {},
            "redmine_auto_pull_enabled": False,
            "redmine_auto_pull_interval_minutes": _int_env("REDMINE_AUTO_PULL_INTERVAL_MINUTES", 30),
            "redmine_auto_pull_ticket_statuses": ["tech_processing", "field_verification", "pending_close"],
        },
    }

    @staticmethod
    def _mask_secret(value: str | None) -> str:
        if not value:
            return ""
        return "******"

    async def _get_or_create_section(self, section: str) -> SystemSettingItem:
        if section not in self._SECTIONS:
            raise HTTPException(status_code=400, detail="无效的配置分组")
        try:
            item, created = await SystemSettingItem.get_or_create(
                section=section,
                defaults={"data": self._DEFAULTS[section]},
            )
            if created:
                logger.info("[settings] create section={}", section)
            return item
        except IntegrityError:
            # Concurrent startup can race on the unique section key; the winner
            # already inserted the row, so the loser should simply reuse it.
            item = await SystemSettingItem.filter(section=section).first()
            if item:
                return item
            raise

    async def _ensure_all_sections(self) -> dict[str, dict]:
        merged: dict[str, dict] = {}
        for section in self._SECTIONS:
            item = await self._get_or_create_section(section)
            data = dict(self._DEFAULTS[section])
            data.update(item.data or {})
            if section == "webdav":
                data.pop("webdav_public_base_url", None)
            merged[section] = data
        return merged

    async def get_safe_dict(self) -> dict:
        sections = await self._ensure_all_sections()
        data = {}
        for section_data in sections.values():
            data.update(section_data)
        data["smtp_password"] = self._mask_secret(data.get("smtp_password"))
        data["webdav_password"] = self._mask_secret(data.get("webdav_password"))
        data["db_backup_webdav_password"] = self._mask_secret(data.get("db_backup_webdav_password"))
        data["redmine_api_key"] = self._mask_secret(data.get("redmine_api_key"))
        return data

    async def get_public_config(self) -> dict:
        try:
            cached = await execute_redis("get", self.PUBLIC_CONFIG_CACHE_KEY)
            if cached:
                return json.loads(cached)
        except Exception as exc:
            logger.warning("[settings.public_config] cache_read_failed key={} error={}", self.PUBLIC_CONFIG_CACHE_KEY, str(exc))

        sections = await self._ensure_all_sections()
        site = sections["site"]
        ticket = sections["ticket"]
        login_security = sections["login_security"]
        logo_url = "/api/v1/base/site_logo" if site.get("site_logo") else ""
        required_categories = login_security.get("password_required_categories") or ["letter", "digit"]
        legacy_register_enabled = site.get("allow_partner_register", True)
        allow_channel_register = site.get("allow_channel_register", legacy_register_enabled)
        allow_user_register = site.get("allow_user_register", legacy_register_enabled)
        result = {
            "site_title": site.get("site_title"),
            "site_logo": logo_url,
            "allow_partner_register": allow_channel_register or allow_user_register,
            "allow_channel_register": allow_channel_register,
            "allow_user_register": allow_user_register,
            "customer_service_auto_approve_register": site.get("customer_service_auto_approve_register", False),
            "ticket_attachment_extensions": ticket.get("ticket_attachment_extensions") or [],
            "ticket_project_phases": ticket.get("ticket_project_phases") or [],
            "ticket_cs_review_project_phases": ticket.get("ticket_cs_review_project_phases") or [],
            "ticket_issue_types": ticket.get("ticket_issue_types") or [],
            "ticket_impact_scopes": ticket.get("ticket_impact_scopes") or [],
            "ticket_categories": ticket.get("ticket_categories") or [],
            "customer_service_auto_approve_ticket": ticket.get("customer_service_auto_approve_ticket", False),
            "ticket_root_causes": ticket.get("ticket_root_causes") or [],
            "ticket_description_templates": ticket.get("ticket_description_templates") or [],
            "login_security_enabled": login_security.get("login_security_enabled", True),
            "login_account_ip_fail_limit": login_security.get("login_account_ip_fail_limit", 5),
            "login_account_ip_lock_minutes": login_security.get("login_account_ip_lock_minutes", 60),
            "login_ip_fail_limit": login_security.get("login_ip_fail_limit", 20),
            "login_ip_lock_minutes": login_security.get("login_ip_lock_minutes", 60),
            "login_fail_window_minutes": login_security.get("login_fail_window_minutes", 60),
            "login_generic_error_enabled": login_security.get("login_generic_error_enabled", True),
            "user_token_expire_minutes": login_security.get("user_token_expire_minutes", 60),
            "inactive_user_auto_disable_enabled": login_security.get("inactive_user_auto_disable_enabled", True),
            "inactive_user_auto_disable_days": login_security.get("inactive_user_auto_disable_days", 30),
            "password_min_length": login_security.get("password_min_length", 8),
            "password_required_categories": required_categories,
            "password_min_category_count": len(required_categories),
        }
        try:
            await execute_redis("setex", self.PUBLIC_CONFIG_CACHE_KEY, self.PUBLIC_CONFIG_CACHE_TTL_SECONDS, json.dumps(result, ensure_ascii=False))
        except Exception as exc:
            logger.warning("[settings.public_config] cache_write_failed key={} error={}", self.PUBLIC_CONFIG_CACHE_KEY, str(exc))
        return result

    async def _get_merged_raw(self) -> dict:
        sections = await self._ensure_all_sections()
        data = {}
        for section_data in sections.values():
            data.update(section_data)
        return data

    async def get_full_dict(self) -> dict:
        return await self._get_merged_raw()

    async def get_time_sync_status(self) -> dict:
        data = await self._get_merged_raw()
        return time_sync_service.status(data)

    async def sync_time(self) -> dict:
        data = await self._get_merged_raw()
        return time_sync_service.sync(data)

    async def test_webdav_connection(self, payload: dict | None = None) -> dict:
        db_data = await self._get_merged_raw()
        req_data = payload or {}

        enabled = req_data.get("webdav_enabled", db_data.get("webdav_enabled"))
        base_url = req_data.get("webdav_base_url") if req_data.get("webdav_base_url") is not None else db_data.get("webdav_base_url")
        username = req_data.get("webdav_username") if req_data.get("webdav_username") is not None else db_data.get("webdav_username")
        pwd_input = req_data.get("webdav_password")
        if pwd_input == "******":
            password = db_data.get("webdav_password")
        elif pwd_input is None:
            password = db_data.get("webdav_password")
        else:
            password = pwd_input

        if not enabled:
            raise HTTPException(status_code=400, detail="WebDAV未启用，请先开启")
        if not base_url:
            raise HTTPException(status_code=400, detail="WebDAV Base URL 未配置")
        base_url = normalize_webdav_base_url(base_url)
        if not username or not password:
            raise HTTPException(status_code=400, detail="WebDAV账号或密码未配置")

        test_url = base_url.rstrip("/") + quote("/", safe="/")
        body = """<?xml version=\"1.0\" encoding=\"utf-8\" ?><d:propfind xmlns:d=\"DAV:\"><d:allprop/></d:propfind>"""

        logger.info("[settings.webdav.test] start base_url={} username={}", base_url, username)
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.request(
                    "PROPFIND",
                    test_url,
                    content=body,
                    headers={"Depth": "0", "Content-Type": "application/xml"},
                    auth=(username, password),
                )
        except Exception as exc:
            logger.exception("[settings.webdav.test] network_error base_url={} username={} error={}", base_url, username, repr(exc))
            raise HTTPException(status_code=400, detail="连接失败，请检查服务地址和网络")

        if response.status_code not in {200, 207}:
            raise HTTPException(status_code=400, detail=f"连接失败，HTTP状态码：{response.status_code}")

        return {"ok": True, "status_code": response.status_code, "message": "WebDAV连接成功"}

    async def update(self, payload: dict) -> None:
        logger.info("[settings.update] start keys={}", sorted(list(payload.keys())))
        sections = await self._ensure_all_sections()

        if payload.get("smtp_password") == "******":
            payload["smtp_password"] = sections["mail"].get("smtp_password")
        if payload.get("webdav_password") == "******":
            payload["webdav_password"] = sections["webdav"].get("webdav_password")
        if payload.get("db_backup_webdav_password") == "******":
            payload["db_backup_webdav_password"] = sections["database_backup"].get("db_backup_webdav_password")
        if payload.get("redmine_api_key") == "******":
            payload["redmine_api_key"] = sections["redmine"].get("redmine_api_key")
        if payload.get("webdav_base_url"):
            payload["webdav_base_url"] = normalize_webdav_base_url(payload.get("webdav_base_url"))
        if payload.get("db_backup_webdav_base_url"):
            payload["db_backup_webdav_base_url"] = normalize_webdav_base_url(payload.get("db_backup_webdav_base_url"))

        if "allow_channel_register" not in payload and "allow_user_register" not in payload and "allow_partner_register" in payload:
            payload["allow_channel_register"] = payload["allow_partner_register"]
            payload["allow_user_register"] = payload["allow_partner_register"]
        if "allow_channel_register" in payload or "allow_user_register" in payload:
            current_site = sections["site"]
            channel_enabled = payload.get(
                "allow_channel_register",
                current_site.get("allow_channel_register", current_site.get("allow_partner_register", True)),
            )
            user_enabled = payload.get(
                "allow_user_register",
                current_site.get("allow_user_register", current_site.get("allow_partner_register", True)),
            )
            payload["allow_partner_register"] = bool(channel_enabled or user_enabled)

        if "ticket_cs_review_project_phases" in payload:
            current_ticket = sections["ticket"]
            allowed_phases = set(payload.get("ticket_project_phases") or current_ticket.get("ticket_project_phases") or [])
            invalid_phases = [item for item in payload.get("ticket_cs_review_project_phases") or [] if item not in allowed_phases]
            if invalid_phases:
                raise HTTPException(status_code=400, detail="客服审核项目阶段必须包含在项目阶段中")

        site_keys = {
            "site_title",
            "site_logo",
            "allow_partner_register",
            "allow_channel_register",
            "allow_user_register",
            "customer_service_auto_approve_register",
        }
        ticket_keys = {
            "ticket_attachment_extensions",
            "ticket_project_phases",
            "ticket_cs_review_project_phases",
            "ticket_issue_types",
            "ticket_impact_scopes",
            "ticket_categories",
            "customer_service_auto_approve_ticket",
            "ticket_root_causes",
            "ticket_description_templates",
        }
        login_keys = {
            "login_security_enabled",
            "login_account_ip_fail_limit",
            "login_account_ip_lock_minutes",
            "login_ip_fail_limit",
            "login_ip_lock_minutes",
            "login_fail_window_minutes",
            "login_generic_error_enabled",
            "user_token_expire_minutes",
            "inactive_user_auto_disable_enabled",
            "inactive_user_auto_disable_days",
            "password_min_length",
            "password_required_categories",
        }
        time_sync_keys = {
            "time_sync_enabled",
            "time_sync_server",
            "time_sync_interval_minutes",
            "time_sync_max_offset_seconds",
            "time_sync_timezone",
        }
        ticket_notify_keys = {"ticket_notify_by_role"}
        mail_keys = {
            "smtp_host",
            "smtp_port",
            "smtp_username",
            "smtp_password",
            "smtp_sender",
            "smtp_sender_name",
            "smtp_use_tls",
            "smtp_use_ssl",
        }
        mail_template_keys = {
            "email_verify_subject",
            "email_verify_is_html",
            "email_verify_template",
            "register_review_approve_subject",
            "register_review_approve_is_html",
            "register_review_approve_template",
            "register_review_reject_subject",
            "register_review_reject_is_html",
            "register_review_reject_template",
            "reset_password_subject",
            "reset_password_is_html",
            "reset_password_template",
            "admin_reset_password_subject",
            "admin_reset_password_is_html",
            "admin_reset_password_template",
            "ticket_notify_subject",
            "ticket_notify_is_html",
            "ticket_notify_template",
        }
        webdav_keys = {
            "webdav_enabled",
            "webdav_base_url",
            "webdav_username",
            "webdav_password",
            "webdav_share_default_expire_hours",
            "webdav_signature_ttl",
            "webdav_max_upload_size",
            "webdav_signature_secret",
        }
        database_backup_keys = {
            "db_backup_enabled",
            "db_backup_directory",
            "db_backup_mysql_container",
            "db_backup_webdav_base_url",
            "db_backup_webdav_username",
            "db_backup_webdav_password",
            "db_backup_run_at",
            "db_backup_retention_days",
        }
        redmine_keys = {
            "redmine_enabled",
            "redmine_base_url",
            "redmine_api_key",
            "redmine_project_id",
            "redmine_tracker_id",
            "redmine_priority_id",
            "redmine_assigned_to_id",
            "redmine_project_phase_field_id",
            "redmine_os_field_id",
            "redmine_sync_visible_fields",
            "redmine_sync_options",
            "redmine_auto_pull_enabled",
            "redmine_auto_pull_interval_minutes",
            "redmine_auto_pull_ticket_statuses",
        }
        mapping = {
            "site": site_keys,
            "ticket": ticket_keys,
            "login_security": login_keys,
            "time_sync": time_sync_keys,
            "ticket_notify": ticket_notify_keys,
            "mail": mail_keys,
            "mail_template": mail_template_keys,
            "webdav": webdav_keys,
            "database_backup": database_backup_keys,
            "redmine": redmine_keys,
        }

        for section, keys in mapping.items():
            item = await self._get_or_create_section(section)
            merged = dict(self._DEFAULTS[section])
            merged.update(item.data or {})
            if section == "webdav":
                merged.pop("webdav_public_base_url", None)
            for key in keys:
                if key in payload:
                    merged[key] = payload[key]
            if section == "ticket":
                project_phases = merged.get("ticket_project_phases") or []
                review_phases = merged.get("ticket_cs_review_project_phases") or []
                merged["ticket_cs_review_project_phases"] = [item for item in review_phases if item in project_phases]
            item.data = merged
            await item.save()

        try:
            await execute_redis("delete", self.PUBLIC_CONFIG_CACHE_KEY)
        except Exception as exc:
            logger.warning("[settings.update] cache_delete_failed key={} error={}", self.PUBLIC_CONFIG_CACHE_KEY, str(exc))
        await self._sync_redmine_metadata_cache()

    async def _sync_redmine_metadata_cache(self) -> None:
        try:
            raw = await execute_redis("get", self.REDMINE_METADATA_CACHE_KEY)
            if not raw:
                return
            metadata = json.loads(raw)
            redmine = (await self._ensure_all_sections())["redmine"]
            metadata["redmine_os_field_id"] = redmine.get("redmine_os_field_id")
            metadata["redmine_sync_options"] = redmine.get("redmine_sync_options") or {}
            await execute_redis(
                "setex",
                self.REDMINE_METADATA_CACHE_KEY,
                self.REDMINE_METADATA_CACHE_TTL_SECONDS,
                json.dumps(metadata, ensure_ascii=False),
            )
        except Exception as exc:
            logger.warning("[settings.redmine.metadata] cache_sync_failed key={} error={}", self.REDMINE_METADATA_CACHE_KEY, str(exc))

    async def get_logo_abs_path(self) -> str:
        site = (await self._ensure_all_sections())["site"]
        site_logo = site.get("site_logo")
        if not site_logo:
            raise HTTPException(status_code=404, detail="未配置站点Logo")

        abs_path = os.path.normcase(os.path.realpath(os.path.join(settings.UPLOAD_DIR, site_logo)))
        upload_root = os.path.normcase(os.path.realpath(settings.UPLOAD_DIR))
        try:
            in_root = os.path.commonpath([abs_path, upload_root]) == upload_root
        except ValueError:
            in_root = False
        if not in_root:
            raise HTTPException(status_code=400, detail="Logo路径非法")
        if not os.path.exists(abs_path):
            raise HTTPException(status_code=404, detail="Logo文件不存在")
        return abs_path

    async def upload_logo(self, file: UploadFile) -> str:
        logger.info("[settings.logo] start filename={} content_type={}", file.filename, file.content_type)
        ext = normalize_ext(file.filename or "")
        if ext not in {"jpg", "jpeg", "png", "webp"}:
            raise HTTPException(status_code=400, detail="Logo仅支持 jpg/jpeg/png/webp（并按magic头校验）")

        now = datetime.now()
        rel_dir = os.path.join("site", "logo", now.strftime("%Y"), now.strftime("%m"), now.strftime("%d"))
        abs_dir = os.path.join(settings.UPLOAD_DIR, rel_dir)
        os.makedirs(abs_dir, exist_ok=True)

        filename = f"{uuid.uuid4().hex}.{ext}"
        rel_path = os.path.join(rel_dir, filename).replace("\\", "/")
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
                        raise HTTPException(status_code=400, detail="Logo文件大小超限")
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
            raise HTTPException(status_code=500, detail=f"保存Logo失败: {exc}")

        detected_ext = detect_file_type(head)
        if not detected_ext:
            raise HTTPException(status_code=400, detail="无法识别Logo magic头")
        if detected_ext == "svg":
            try:
                os.remove(abs_path)
            except OSError:
                pass
            raise HTTPException(status_code=400, detail="Logo不支持SVG（无法通过magic头可靠校验）")
        if detected_ext != ext and not ({detected_ext, ext} <= {"jpg", "jpeg"}):
            try:
                os.remove(abs_path)
            except OSError:
                pass
            raise HTTPException(status_code=400, detail=f"Logo文件magic头与扩展名不匹配，检测到真实类型为 {detected_ext}")

        item = await self._get_or_create_section("site")
        merged = dict(self._DEFAULTS["site"])
        merged.update(item.data or {})
        merged["site_logo"] = rel_path
        item.data = merged
        await item.save()
        try:
            await execute_redis("delete", self.PUBLIC_CONFIG_CACHE_KEY)
        except Exception as exc:
            logger.warning("[settings.logo] cache_delete_failed key={} error={}", self.PUBLIC_CONFIG_CACHE_KEY, str(exc))
        return rel_path


system_setting_controller = SystemSettingController()
