from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import TicketStatus


class SystemSettingUpdateIn(BaseModel):
    site_title: str = Field(..., description="网站标题")
    site_logo: str | None = Field(default=None, description="网站Logo")
    allow_partner_register: bool = Field(default=True, description="是否开放代理商注册")
    allow_channel_register: bool = Field(default=True, description="是否开放渠道商注册")
    allow_user_register: bool = Field(default=True, description="是否开放用户注册")
    customer_service_auto_approve_register: bool = Field(default=False, description="客服是否自动审批注册")
    ticket_attachment_extensions: list[str] = Field(default_factory=list, description="工单附件允许上传类型")
    ticket_project_phases: list[str] = Field(default_factory=list, description="工单项目阶段")
    ticket_cs_review_project_phases: list[str] = Field(default_factory=list, description="工单客服审核项目阶段")
    ticket_issue_types: list[str] = Field(default_factory=list, description="工单跟踪")
    ticket_impact_scopes: list[str] = Field(default_factory=list, description="工单影响范围")
    ticket_categories: list[str] = Field(default_factory=list, description="工单分类")
    customer_service_auto_approve_ticket: bool = Field(default=False, description="客服是否自动审批工单")
    ticket_root_causes: list[str] = Field(default_factory=list, description="工单问题根因")
    ticket_description_templates: list[str] = Field(default_factory=list, description="工单问题描述模板")
    login_security_enabled: bool = Field(default=True, description="是否启用登录安全策略")
    login_challenge_enabled: bool = Field(default=True, description="是否启用人机校验")
    login_challenge_type: str = Field(default="captcha", description="人机校验方式")
    turnstile_site_key: str | None = Field(default=None, description="Cloudflare Turnstile Site Key")
    turnstile_secret_key: str | None = Field(default=None, description="Cloudflare Turnstile Secret Key")
    login_account_ip_fail_limit: int = Field(default=5, description="账号+IP失败锁定阈值")
    login_account_ip_lock_minutes: int = Field(default=60, description="账号+IP锁定时长(分钟)")
    login_ip_fail_limit: int = Field(default=20, description="IP失败锁定阈值")
    login_ip_lock_minutes: int = Field(default=60, description="IP锁定时长(分钟)")
    login_fail_window_minutes: int = Field(default=60, description="登录失败统计窗口(分钟)")
    login_generic_error_enabled: bool = Field(default=True, description="是否启用统一登录错误提示")
    user_token_expire_minutes: int = Field(default=60, description="用户Token失效时间(分钟)")
    inactive_user_auto_disable_enabled: bool = Field(default=True, description="是否启用未登录用户自动禁用")
    inactive_user_auto_disable_days: int = Field(default=30, description="未登录用户自动禁用天数")
    password_min_length: int = Field(default=8, description="密码最小长度")
    password_required_categories: list[str] = Field(default_factory=lambda: ["letter", "digit"], description="密码必选类别")
    time_sync_enabled: bool = Field(default=True, description="是否启用时间同步配置")
    time_sync_server: str = Field(default="ntp.aliyun.com", description="时间服务器")
    time_sync_interval_minutes: int = Field(default=60, description="时间同步间隔(分钟)")
    time_sync_max_offset_seconds: int = Field(default=5, description="最大允许偏差(秒)")
    time_sync_timezone: str = Field(default="Asia/Shanghai", description="系统时区")

    ticket_notify_by_role: dict[str, list[str]] = Field(default_factory=dict, description="按角色配置工单提醒节点")

    smtp_host: str | None = None
    smtp_port: int = 465
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_sender: str | None = None
    smtp_sender_name: str = "系统通知"
    smtp_use_tls: bool = False
    smtp_use_ssl: bool = True

    email_verify_subject: str = "代理商注册验证码"
    email_verify_is_html: bool = True
    email_verify_template: str = "您好，您的验证码是：{code}，{minutes}分钟内有效。"
    register_review_approve_subject: str = "注册审核结果通知"
    register_review_approve_is_html: bool = True
    register_review_approve_template: str = (
        "您好，{contact_name}，您的{register_type}注册申请已审核通过，现可使用邮箱登录系统。"
    )
    register_review_reject_subject: str = "注册审核结果通知"
    register_review_reject_is_html: bool = True
    register_review_reject_template: str = "您好，{contact_name}，您的{register_type}注册申请已驳回。驳回理由：{reason}"
    reset_password_subject: str = "密码重置验证码"
    reset_password_is_html: bool = False
    reset_password_template: str = "<div style=\"font-family:Arial,'PingFang SC','Microsoft YaHei',sans-serif;color:#1f2937;line-height:1.7;\"><h2 style=\"margin:0 0 12px;font-size:18px;color:#0f4c81;\">找回密码验证码</h2><p style=\"margin:0 0 10px;\">您好，您正在进行密码重置操作，请使用以下验证码：</p><div style=\"display:inline-block;padding:10px 18px;border-radius:8px;background:#eff6ff;border:1px solid #bfdbfe;font-size:24px;font-weight:700;letter-spacing:4px;color:#1d4ed8;\">{code}</div><p style=\"margin:12px 0 0;color:#6b7280;\">验证码 {minutes} 分钟内有效，请勿泄露给他人。</p></div>"
    admin_reset_password_subject: str = "账号密码已重置"
    admin_reset_password_is_html: bool = True
    admin_reset_password_template: str = "<div style=\"font-family:Arial,'PingFang SC','Microsoft YaHei',sans-serif;color:#1f2937;line-height:1.7;\"><h2 style=\"margin:0 0 12px;font-size:18px;color:#b45309;\">账号密码已重置</h2><p style=\"margin:0 0 8px;\">您好，<b>{username}</b>：</p><p style=\"margin:0 0 8px;\">管理员已重置您的账号密码，请使用以下临时密码登录：</p><div style=\"display:inline-block;padding:10px 14px;border-radius:8px;background:#fff7ed;border:1px solid #fed7aa;font-size:20px;font-weight:700;color:#c2410c;\">{password}</div><p style=\"margin:12px 0 0;color:#6b7280;\">登录后请尽快在个人中心修改密码。</p></div>"
    ticket_notify_subject: str = "工单状态提醒：{ticket_no}"
    ticket_notify_is_html: bool = True
    ticket_notify_template: str = "<div style=\"font-family:Arial,'PingFang SC','Microsoft YaHei',sans-serif;color:#1f2937;line-height:1.7;\"><h2 style=\"margin:0 0 12px;font-size:18px;color:#1d4ed8;\">工单状态提醒</h2><p style=\"margin:0 0 8px;\">您好，<b>{name}</b>：</p><p style=\"margin:0 0 6px;\">工单编号：<b>{ticket_no}</b></p><p style=\"margin:0 0 6px;\">工单标题：{title}</p><p style=\"margin:0 0 6px;\">当前状态：<b style=\"color:#1d4ed8;\">{status}</b></p><p style=\"margin:0 0 6px;\">操作人：{operator}</p><p style=\"margin:8px 0 0;color:#6b7280;\">请及时登录系统处理。</p></div>"

    webdav_enabled: bool = False
    webdav_base_url: str | None = None
    webdav_username: str | None = None
    webdav_password: str | None = None
    webdav_share_default_expire_hours: int = 168
    webdav_signature_ttl: int = 24
    webdav_max_upload_size: int = 50 * 1024 * 1024
    webdav_signature_secret: str | None = None

    db_backup_enabled: bool = False
    db_backup_directory: str = "/iandsec-db-backups"
    db_backup_mysql_container: str = "iandsec-uc-mysql"
    db_backup_webdav_base_url: str | None = None
    db_backup_webdav_username: str | None = None
    db_backup_webdav_password: str | None = None
    db_backup_run_at: str = "02:30"
    db_backup_retention_days: int = 7
    redmine_enabled: bool = False
    redmine_base_url: str | None = None
    redmine_api_key: str | None = None
    redmine_project_id: str | None = None
    redmine_tracker_id: int | None = None
    redmine_priority_id: int | None = None
    redmine_assigned_to_id: int | None = None
    redmine_closed_status_id: int | None = None
    redmine_project_phase_field_id: int | None = None
    redmine_os_field_id: int | None = None
    redmine_server_version_field_id: int | None = None
    redmine_client_version_field_id: int | None = None
    redmine_sync_visible_fields: list[str] = Field(default_factory=list)
    redmine_sync_options: dict[str, list[str]] = Field(default_factory=dict)
    redmine_auto_pull_enabled: bool = False
    redmine_auto_pull_interval_minutes: int = 120
    redmine_auto_pull_ticket_statuses: list[str] = Field(
        default_factory=lambda: [
            TicketStatus.TECH_PROCESSING.value,
            TicketStatus.FIELD_VERIFICATION.value,
            TicketStatus.PENDING_CLOSE.value,
        ]
    )

    @field_validator("ticket_attachment_extensions")
    @classmethod
    def validate_attachment_extensions(cls, value: list[str]):
        items = []
        for item in value:
            normalized = str(item or "").strip().lower().lstrip(".")
            if normalized:
                items.append(normalized)
        if not items:
            raise ValueError("允许上传类型至少保留一项")
        return items

    @field_validator("ticket_root_causes", "ticket_description_templates")
    @classmethod
    def validate_required_ticket_items(cls, value: list[str], info):
        field_name = "问题根因" if info.field_name == "ticket_root_causes" else "问题描述模板"
        items = [item.strip() for item in value if isinstance(item, str) and item.strip()]
        if not items:
            raise ValueError(f"{field_name}至少保留一项")
        return items

    @field_validator("ticket_project_phases", "ticket_cs_review_project_phases", "ticket_issue_types", "ticket_impact_scopes")
    @classmethod
    def normalize_ticket_option_items(cls, value: list[str]):
        items: list[str] = []
        for item in value or []:
            text = str(item or "").strip()
            if text and text not in items:
                items.append(text)
        return items

    @model_validator(mode="after")
    def validate_ticket_phase_relationships(self):
        if "ticket_project_phases" in self.model_fields_set and not self.ticket_project_phases:
            raise ValueError("项目阶段至少保留一项")
        if "ticket_cs_review_project_phases" in self.model_fields_set and not self.ticket_cs_review_project_phases:
            raise ValueError("客服审核项目阶段至少保留一项")
        if "ticket_issue_types" in self.model_fields_set and not self.ticket_issue_types:
            raise ValueError("跟踪至少保留一项")
        if "ticket_impact_scopes" in self.model_fields_set and not self.ticket_impact_scopes:
            raise ValueError("影响范围至少保留一项")
        if (
            "ticket_project_phases" in self.model_fields_set
            and "ticket_cs_review_project_phases" in self.model_fields_set
            and self.ticket_cs_review_project_phases
        ):
            project_phases = set(self.ticket_project_phases or [])
            invalid = [item for item in self.ticket_cs_review_project_phases if item not in project_phases]
            if invalid:
                raise ValueError("客服审核项目阶段必须包含在项目阶段中")
        return self

    @field_validator(
        "login_account_ip_fail_limit",
        "login_account_ip_lock_minutes",
        "login_ip_fail_limit",
        "login_ip_lock_minutes",
        "login_fail_window_minutes",
        "user_token_expire_minutes",
        "inactive_user_auto_disable_days",
    )
    @classmethod
    def validate_positive_security_numbers(cls, value: int, info):
        if value < 1:
            raise ValueError(f"{info.field_name} 必须大于等于 1")
        if info.field_name == "user_token_expire_minutes" and value > 30 * 24 * 60:
            raise ValueError("用户Token失效时间不能超过30天")
        if info.field_name == "inactive_user_auto_disable_days" and value > 3650:
            raise ValueError("未登录自动禁用天数不能超过3650天")
        return value

    @field_validator("password_min_length")
    @classmethod
    def validate_password_min_length(cls, value: int):
        if value < 8:
            raise ValueError("密码最小长度必须大于等于8")
        return value

    @field_validator("password_required_categories")
    @classmethod
    def validate_password_required_categories(cls, value: list[str]):
        valid = {"letter", "digit", "special"}
        normalized = []
        for item in value or []:
            k = str(item or "").strip().lower()
            if not k:
                continue
            if k not in valid:
                raise ValueError("密码类别仅支持 letter/digit/special")
            if k not in normalized:
                normalized.append(k)
        if not normalized:
            raise ValueError("密码类别至少选择一项")
        return normalized

    @field_validator("time_sync_server", "time_sync_timezone")
    @classmethod
    def validate_time_sync_text(cls, value: str, info):
        text = str(value or "").strip()
        if not text:
            raise ValueError(f"{info.field_name} 不能为空")
        if len(text) > 128:
            raise ValueError(f"{info.field_name} 不能超过128个字符")
        return text

    @field_validator("time_sync_interval_minutes", "time_sync_max_offset_seconds")
    @classmethod
    def validate_positive_time_sync_numbers(cls, value: int, info):
        if value < 1:
            raise ValueError(f"{info.field_name} 必须大于等于 1")
        return value

    @field_validator("ticket_notify_by_role")
    @classmethod
    def validate_ticket_notify_by_role(cls, value: dict[str, list[str]]):
        valid_statuses = {item.value for item in TicketStatus}
        normalized: dict[str, list[str]] = {}
        for role_name, statuses in (value or {}).items():
            role = str(role_name or "").strip()
            if not role:
                continue
            role_statuses: list[str] = []
            for item in statuses or []:
                status = str(item or "").strip()
                if not status:
                    continue
                if status not in valid_statuses:
                    raise ValueError("工单邮件通知节点包含非法状态")
                if status not in role_statuses:
                    role_statuses.append(status)
            normalized[role] = role_statuses
        return normalized

    @field_validator("webdav_share_default_expire_hours", "webdav_signature_ttl", "webdav_max_upload_size")
    @classmethod
    def validate_positive_webdav_numbers(cls, value: int, info):
        if value < 1:
            raise ValueError(f"{info.field_name} 必须大于等于 1")
        if info.field_name == "webdav_signature_ttl" and value > 9999:
            raise ValueError("WebDAV signature ttl must be less than or equal to 9999 hours")
        return value

    @field_validator("db_backup_directory")
    @classmethod
    def validate_db_backup_directory(cls, value: str):
        text = str(value or "").strip()
        if not text:
            raise ValueError("数据库备份目录不能为空")
        if len(text) > 500:
            raise ValueError("数据库备份目录不能超过500个字符")
        return text

    @field_validator("db_backup_mysql_container")
    @classmethod
    def validate_db_backup_mysql_container(cls, value: str):
        text = str(value or "").strip()
        if not text:
            raise ValueError("MySQL容器名不能为空")
        if len(text) > 128:
            raise ValueError("MySQL容器名不能超过128个字符")
        return text

    @field_validator("db_backup_webdav_base_url", "db_backup_webdav_username", "db_backup_webdav_password")
    @classmethod
    def validate_db_backup_webdav_text(cls, value: str | None, info):
        if value is None:
            return value
        text = str(value).strip()
        if not text:
            return None
        if len(text) > 500:
            raise ValueError(f"{info.field_name}不能超过500个字符")
        return text

    @field_validator("db_backup_run_at")
    @classmethod
    def validate_db_backup_run_at(cls, value: str):
        text = str(value or "").strip()
        try:
            hour_text, minute_text = text.split(":", 1)
            hour = int(hour_text)
            minute = int(minute_text)
            if hour < 0 or hour > 23 or minute < 0 or minute > 59:
                raise ValueError("out of range")
        except Exception:
            raise ValueError("数据库备份执行时间格式必须为 HH:mm")
        return f"{hour:02d}:{minute:02d}"

    @field_validator("db_backup_retention_days")
    @classmethod
    def validate_db_backup_retention_days(cls, value: int):
        if value < 1 or value > 365:
            raise ValueError("数据库备份保留天数必须在1到365之间")
        return value


    @field_validator("turnstile_site_key", "turnstile_secret_key", "redmine_base_url", "redmine_api_key", "redmine_project_id")
    @classmethod
    def validate_redmine_text(cls, value: str | None, info):
        if value is None:
            return value
        text = str(value).strip()
        if not text:
            return None
        if len(text) > 500:
            raise ValueError(f"{info.field_name} 不能超过500个字符")
        return text

    @field_validator("login_challenge_type")
    @classmethod
    def validate_login_challenge_type(cls, value: str):
        text = str(value or "").strip().lower()
        if text not in {"captcha", "turnstile", "both"}:
            raise ValueError("人机校验方式仅支持 captcha/turnstile/both")
        return text

    @field_validator(
        "redmine_tracker_id",
        "redmine_priority_id",
        "redmine_assigned_to_id",
        "redmine_closed_status_id",
        "redmine_project_phase_field_id",
        "redmine_os_field_id",
        "redmine_server_version_field_id",
        "redmine_client_version_field_id",
    )
    @classmethod
    def validate_redmine_ids(cls, value: int | None, info):
        if value is None:
            return value
        if value < 1:
            raise ValueError(f"{info.field_name} 必须大于等于1")
        return value

    @field_validator("redmine_auto_pull_interval_minutes")
    @classmethod
    def validate_redmine_auto_pull_interval_minutes(cls, value: int):
        if value < 1 or value > 1440:
            raise ValueError("Redmine定时拉取间隔必须在1到1440分钟之间")
        return value

    @field_validator("redmine_auto_pull_ticket_statuses")
    @classmethod
    def validate_redmine_auto_pull_ticket_statuses(cls, value: list[str]):
        valid_statuses = {item.value for item in TicketStatus}
        result = []
        for item in value or []:
            status = str(item or "").strip()
            if not status:
                continue
            if status not in valid_statuses:
                raise ValueError("Redmine定时拉取工单状态包含非法值")
            if status not in result:
                result.append(status)
        if not result:
            raise ValueError("Redmine定时拉取工单状态至少选择一项")
        return result

    @field_validator("redmine_sync_visible_fields")
    @classmethod
    def validate_redmine_sync_visible_fields(cls, value: list[str]):
        allowed = {"project_id", "tracker_id", "priority_id", "assigned_to_id", "project_phase", "os"}
        result = []
        for item in value or []:
            text = str(item or "").strip()
            if text in allowed and text not in result:
                result.append(text)
        return result

    @field_validator("redmine_sync_options", mode="before")
    @classmethod
    def validate_redmine_sync_options(cls, value):
        allowed = {"project_id", "tracker_id", "priority_id", "assigned_to_id", "project_phase", "os"}
        result = {}
        for key, values in (value or {}).items():
            field = str(key or "").strip()
            if field not in allowed:
                continue
            items = []
            for item in values or []:
                text = str(item or "").strip()
                if text and text not in items:
                    items.append(text)
            if items:
                result[field] = items
        return result


class PublicSiteConfigOut(BaseModel):
    site_title: str
    site_logo: str | None = None
    allow_partner_register: bool
    allow_channel_register: bool
    allow_user_register: bool
    customer_service_auto_approve_register: bool
    ticket_attachment_extensions: list[str]
    ticket_project_phases: list[str]
    ticket_cs_review_project_phases: list[str]
    ticket_issue_types: list[str]
    ticket_impact_scopes: list[str]
    ticket_categories: list[str]
    customer_service_auto_approve_ticket: bool
    ticket_description_templates: list[str]
    login_security_enabled: bool
    login_challenge_enabled: bool
    login_challenge_type: str
    turnstile_site_key: str
    login_account_ip_fail_limit: int
    login_account_ip_lock_minutes: int
    login_ip_fail_limit: int
    login_ip_lock_minutes: int
    login_fail_window_minutes: int
    login_generic_error_enabled: bool
    user_token_expire_minutes: int
    inactive_user_auto_disable_enabled: bool
    inactive_user_auto_disable_days: int
    password_min_length: int
    password_required_categories: list[str]
    ticket_notify_by_role: dict[str, list[str]]


class WebDavTestIn(BaseModel):
    webdav_enabled: bool = True
    webdav_base_url: str | None = None
    webdav_username: str | None = None
    webdav_password: str | None = None


class RedmineMetadataIn(BaseModel):
    redmine_base_url: str | None = None
    redmine_api_key: str | None = None

    @field_validator("redmine_base_url", "redmine_api_key")
    @classmethod
    def validate_redmine_metadata_text(cls, value: str | None, info):
        if value is None:
            return value
        text = str(value).strip()
        if not text:
            return None
        if len(text) > 500:
            raise ValueError(f"{info.field_name} 不能超过500个字符")
        return text


class DatabaseBackupConfigIn(BaseModel):
    db_backup_enabled: bool = False
    db_backup_directory: str | None = None
    db_backup_mysql_container: str | None = None
    db_backup_webdav_base_url: str | None = None
    db_backup_webdav_username: str | None = None
    db_backup_webdav_password: str | None = None
    db_backup_run_at: str | None = None
    db_backup_retention_days: int | None = None
