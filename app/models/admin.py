from tortoise import fields

from app.schemas.menus import MenuType

from .base import BaseModel, TimestampMixin
from .enums import (
    MethodType,
    PartnerRegisterStatus,
    RegisterType,
    SkillKnowDocumentStatus,
    SkillKnowMessageRole,
    TicketActionType,
    TicketStatus,
)


class User(BaseModel, TimestampMixin):
    username = fields.CharField(max_length=255, unique=True, description="用户名称", index=True)
    alias = fields.CharField(max_length=30, null=True, description="用户姓名", index=True)
    company_name = fields.CharField(max_length=120, null=True, description="公司名称", index=True)
    hardware_id = fields.CharField(max_length=80, null=True, unique=True, description="产品硬件ID", index=True)
    email = fields.CharField(max_length=255, unique=True, description="邮箱", index=True)
    phone = fields.CharField(max_length=20, null=True, unique=True, description="电话", index=True)
    password = fields.CharField(max_length=128, null=True, description="密码")
    is_active = fields.BooleanField(default=True, description="是否激活", index=True)
    is_superuser = fields.BooleanField(default=False, description="是否为超级管理员", index=True)
    token_version = fields.IntField(default=0, description="令牌版本")
    last_login = fields.DatetimeField(null=True, description="最后登录时间", index=True)
    roles = fields.ManyToManyField("models.Role", related_name="user_roles")
    dept_id = fields.IntField(null=True, description="部门ID", index=True)

    class Meta:
        table = "user"


class Role(BaseModel, TimestampMixin):
    name = fields.CharField(max_length=20, unique=True, description="角色名称", index=True)
    desc = fields.CharField(max_length=500, null=True, description="角色描述")
    menus = fields.ManyToManyField("models.Menu", related_name="role_menus")
    apis = fields.ManyToManyField("models.Api", related_name="role_apis")

    class Meta:
        table = "role"


class Api(BaseModel, TimestampMixin):
    path = fields.CharField(max_length=100, description="API路径", index=True)
    method = fields.CharEnumField(MethodType, description="请求方法", index=True)
    summary = fields.CharField(max_length=500, description="请求简介", index=True)
    tags = fields.CharField(max_length=100, description="API标签", index=True)

    class Meta:
        table = "api"


class Menu(BaseModel, TimestampMixin):
    name = fields.CharField(max_length=20, description="菜单名称", index=True)
    remark = fields.JSONField(null=True, description="保留字段")
    menu_type = fields.CharEnumField(MenuType, null=True, description="菜单类型")
    icon = fields.CharField(max_length=100, null=True, description="菜单图标")
    path = fields.CharField(max_length=100, description="菜单路径", index=True)
    order = fields.IntField(default=0, description="排序", index=True)
    parent_id = fields.IntField(default=0, description="父菜单ID", index=True)
    is_hidden = fields.BooleanField(default=False, description="是否隐藏")
    component = fields.CharField(max_length=100, description="组件")
    keepalive = fields.BooleanField(default=True, description="存活")
    redirect = fields.CharField(max_length=100, null=True, description="重定向")

    class Meta:
        table = "menu"


class Dept(BaseModel, TimestampMixin):
    name = fields.CharField(max_length=20, unique=True, description="部门名称", index=True)
    desc = fields.CharField(max_length=500, null=True, description="备注")
    is_deleted = fields.BooleanField(default=False, description="软删除标记", index=True)
    order = fields.IntField(default=0, description="排序", index=True)
    parent_id = fields.IntField(default=0, max_length=10, description="父部门ID", index=True)

    class Meta:
        table = "dept"


class DeptClosure(BaseModel, TimestampMixin):
    ancestor = fields.IntField(description="父代", index=True)
    descendant = fields.IntField(description="子代", index=True)
    level = fields.IntField(default=0, description="深度", index=True)


class AuditLog(BaseModel, TimestampMixin):
    user_id = fields.IntField(description="用户ID", index=True)
    username = fields.CharField(max_length=64, default="", description="用户名称", index=True)
    module = fields.CharField(max_length=64, default="", description="功能模块", index=True)
    summary = fields.CharField(max_length=128, default="", description="请求描述", index=True)
    method = fields.CharField(max_length=10, default="", description="请求方法", index=True)
    path = fields.CharField(max_length=255, default="", description="请求路径", index=True)
    status = fields.IntField(default=-1, description="状态码", index=True)
    response_time = fields.IntField(default=0, description="响应时间(单位ms)", index=True)
    request_args = fields.JSONField(null=True, description="请求参数")
    response_body = fields.JSONField(null=True, description="返回数据")
    is_archived = fields.BooleanField(default=False, description="是否归档", index=True)


class Ticket(BaseModel, TimestampMixin):
    ticket_no = fields.CharField(max_length=40, unique=True, description="工单编号", index=True)
    company_name = fields.CharField(max_length=120, description="公司名称")
    contact_name = fields.CharField(max_length=60, description="联系人")
    email = fields.CharField(max_length=255, description="邮箱", index=True)
    phone = fields.CharField(max_length=20, description="手机号", index=True)
    project_phase = fields.CharField(max_length=30, description="项目阶段", index=True)
    issue_type = fields.CharField(max_length=30, default="现网问题", description="跟踪", index=True)
    impact_scope = fields.CharField(max_length=30, default="全部", description="影响范围", index=True)
    category = fields.CharField(max_length=60, description="问题分类", index=True)
    title = fields.CharField(max_length=200, description="问题标题", index=True)
    description = fields.TextField(description="问题描述")
    status = fields.CharEnumField(TicketStatus, max_length=32, default=TicketStatus.PENDING_REVIEW, index=True)
    submitter_id = fields.BigIntField(description="提交人ID", index=True)
    reviewer_id = fields.BigIntField(null=True, description="客服审核人ID", index=True)
    tech_id = fields.BigIntField(null=True, description="技术处理人ID", index=True)
    reject_reason = fields.TextField(null=True, description="驳回原因")
    root_cause = fields.CharField(max_length=120, null=True, description="问题根因", index=True)
    finished_at = fields.DatetimeField(null=True, description="完成时间", index=True)

    redmine_issue_id = fields.BigIntField(null=True, description="Redmine Issue ID", index=True)
    redmine_issue_url = fields.CharField(max_length=500, null=True, description="Redmine Issue URL")
    redmine_sync_status = fields.CharField(max_length=20, default="never", description="Redmine sync status", index=True)
    redmine_sync_error = fields.TextField(null=True, description="Redmine sync error")
    redmine_synced_at = fields.DatetimeField(null=True, description="Redmine synced at")
    redmine_last_updated_on = fields.DatetimeField(null=True, description="Redmine last updated on")
    redmine_status_id = fields.BigIntField(null=True, description="Redmine status ID", index=True)
    redmine_status_name = fields.CharField(max_length=120, null=True, description="Redmine status name")

    class Meta:
        table = "ticket"


class TicketAttachment(BaseModel, TimestampMixin):
    ticket_id = fields.BigIntField(null=True, description="工单ID", index=True)
    origin_name = fields.CharField(max_length=255, description="原始文件名")
    file_path = fields.CharField(max_length=500, description="文件相对路径")
    file_size = fields.BigIntField(default=0, description="文件大小")
    mime_type = fields.CharField(max_length=100, default="application/octet-stream", description="MIME类型")
    uploader_id = fields.BigIntField(description="上传人ID", index=True)

    class Meta:
        table = "ticket_attachment"


class TicketActionLog(BaseModel, TimestampMixin):
    ticket_id = fields.BigIntField(description="工单ID", index=True)
    action = fields.CharEnumField(TicketActionType, description="动作类型", index=True)
    from_status = fields.CharEnumField(TicketStatus, null=True, description="变更前状态", index=True)
    to_status = fields.CharEnumField(TicketStatus, description="变更后状态", index=True)
    operator_id = fields.BigIntField(description="操作人ID", index=True)
    comment = fields.TextField(null=True, description="备注")

    class Meta:
        table = "ticket_action_log"


class PartnerRegistration(BaseModel, TimestampMixin):
    register_type = fields.CharEnumField(RegisterType, default=RegisterType.CHANNEL, description="注册类型", index=True)
    company_name = fields.CharField(max_length=120, description="公司名称")
    contact_name = fields.CharField(max_length=60, description="联系人")
    email = fields.CharField(max_length=255, description="邮箱", index=True)
    phone = fields.CharField(max_length=20, description="手机号", index=True)
    username = fields.CharField(max_length=255, description="用户名", index=True)
    hardware_id = fields.CharField(max_length=80, null=True, description="产品硬件ID", index=True)
    password_hash = fields.CharField(max_length=128, description="密码哈希")
    status = fields.CharEnumField(PartnerRegisterStatus, default=PartnerRegisterStatus.PENDING, index=True)
    reviewer_id = fields.BigIntField(null=True, description="审核人ID", index=True)
    review_comment = fields.CharField(max_length=500, null=True, description="审核备注")
    reviewed_at = fields.DatetimeField(null=True, description="审核时间", index=True)

    class Meta:
        table = "partner_registration"


class SystemSettingItem(BaseModel, TimestampMixin):
    section = fields.CharField(max_length=50, unique=True, description="配置分组", index=True)
    data = fields.JSONField(default=dict, description="分组配置JSON")

    class Meta:
        table = "system_setting_item"


class WebDavShareLink(BaseModel, TimestampMixin):
    code = fields.CharField(max_length=32, unique=True, description="分享码", index=True)
    file_path = fields.CharField(max_length=1000, description="文件路径")
    file_name = fields.CharField(max_length=255, description="文件名")
    expire_time = fields.DatetimeField(description="过期时间", index=True)
    is_active = fields.BooleanField(default=True, description="是否生效", index=True)
    created_by = fields.BigIntField(description="创建人ID", index=True)

    class Meta:
        table = "webdav_share_link"


class TerminalAuthReport(BaseModel, TimestampMixin):
    company_name = fields.CharField(max_length=120, description="公司名称", index=True)
    auth_expire_at = fields.DatetimeField(description="授权到期时间", index=True)
    maintain_expire_at = fields.DatetimeField(description="维保到期时间", index=True)
    terminal_stats = fields.JSONField(default=dict, description="终端数量统计")
    client_versions = fields.JSONField(default=dict, description="客户端版本统计")
    server_version = fields.CharField(max_length=120, null=True, description="服务器版本号", index=True)
    reported_at = fields.DatetimeField(description="上报时间", index=True)
    source_ip = fields.CharField(max_length=64, null=True, description="来源IP", index=True)
    raw_payload = fields.JSONField(default=dict, description="原始上报数据")

    class Meta:
        table = "terminal_auth_report"


class TerminalUpgradeConfig(BaseModel, TimestampMixin):
    latest_version = fields.CharField(max_length=120, description="最新版本号", index=True)
    webdav_path = fields.CharField(max_length=1000, description="WebDAV升级包路径")
    enabled = fields.BooleanField(default=True, description="是否启用升级检测", index=True)
    force_upgrade = fields.BooleanField(default=False, description="是否强制升级")
    release_notes = fields.TextField(null=True, description="版本说明")
    report_token = fields.CharField(max_length=255, null=True, description="第三方上报密钥")
    download_expire_hours = fields.IntField(default=168, description="下载链接有效期小时")

    class Meta:
        table = "terminal_upgrade_config"


class GlobalNotice(BaseModel, TimestampMixin):
    title = fields.CharField(max_length=100, null=True, description="通知标题")
    content_html = fields.TextField(description="通知内容HTML")
    target_type = fields.CharField(max_length=10, description="发送范围类型", index=True)
    target_role_ids = fields.JSONField(default=list, description="目标角色ID列表")
    target_user_ids = fields.JSONField(default=list, description="目标用户ID列表")
    created_by = fields.BigIntField(description="创建人ID", index=True)
    is_active = fields.BooleanField(default=True, description="是否生效", index=True)

    class Meta:
        table = "global_notice"


class GlobalNoticeUser(BaseModel, TimestampMixin):
    notice_id = fields.BigIntField(description="通知ID", index=True)
    user_id = fields.BigIntField(description="接收用户ID", index=True)
    is_read = fields.BooleanField(default=False, description="是否已读", index=True)
    read_at = fields.DatetimeField(null=True, description="已读时间", index=True)
    delivered_at = fields.DatetimeField(auto_now_add=True, description="投递时间", index=True)

    class Meta:
        table = "global_notice_user"
        unique_together = ("notice_id", "user_id")


class SkillKnowFolder(BaseModel, TimestampMixin):
    uuid = fields.CharField(max_length=36, unique=True, description="文件夹UUID", index=True)
    name = fields.CharField(max_length=100, description="文件夹名称", index=True)
    description = fields.TextField(null=True, description="文件夹描述")
    parent_id = fields.BigIntField(null=True, description="父文件夹ID", index=True)
    sort_order = fields.IntField(default=0, description="排序", index=True)
    is_system = fields.BooleanField(default=False, description="是否系统文件夹", index=True)

    class Meta:
        table = "sk_folder"


class SkillKnowDocument(BaseModel, TimestampMixin):
    uuid = fields.CharField(max_length=36, unique=True, description="文档UUID", index=True)
    uri = fields.CharField(max_length=500, null=True, unique=True, description="Document URI", index=True)
    title = fields.CharField(max_length=200, description="文档标题", index=True)
    description = fields.TextField(null=True, description="文档描述")
    filename = fields.CharField(max_length=255, description="文件名")
    file_path = fields.CharField(max_length=500, description="文件路径")
    file_size = fields.BigIntField(default=0, description="文件大小")
    file_type = fields.CharField(max_length=50, description="文件类型", index=True)
    abstract = fields.TextField(null=True, description="L0摘要")
    overview = fields.TextField(null=True, description="L1概览")
    content = fields.TextField(null=True, description="L2完整内容")
    content_hash = fields.CharField(max_length=64, null=True, description="内容哈希", index=True)
    status = fields.CharEnumField(
        SkillKnowDocumentStatus,
        default=SkillKnowDocumentStatus.PENDING,
        description="处理状态",
        index=True,
    )
    error_message = fields.TextField(null=True, description="错误信息")
    category = fields.CharField(max_length=100, null=True, description="分类", index=True)
    tags = fields.JSONField(default=list, description="标签")
    folder_id = fields.BigIntField(null=True, description="所属文件夹ID", index=True)
    owner_id = fields.BigIntField(null=True, description="所有者ID", index=True)
    extra_metadata = fields.JSONField(default=dict, description="元数据")
    class Meta:
        table = "sk_document"


class SkillKnowDocumentChunk(BaseModel, TimestampMixin):
    uuid = fields.CharField(max_length=36, unique=True, description="Chunk UUID", index=True)
    document_id = fields.BigIntField(description="文档ID", index=True)
    uri = fields.CharField(max_length=500, unique=True, description="Chunk URI", index=True)
    chunk_index = fields.IntField(description="分块序号", index=True)
    heading = fields.CharField(max_length=300, null=True, description="标题路径")
    content = fields.TextField(description="Markdown分块内容")
    content_hash = fields.CharField(max_length=64, description="内容哈希", index=True)
    token_count = fields.IntField(default=0, description="粗略Token数")
    extra_metadata = fields.JSONField(default=dict, description="元数据")

    class Meta:
        table = "sk_document_chunk"
        unique_together = ("document_id", "chunk_index")


class SkillKnowDocumentSection(BaseModel, TimestampMixin):
    uuid = fields.CharField(max_length=36, unique=True, description="??UUID", index=True)
    document_id = fields.BigIntField(description="??ID", index=True)
    section_key = fields.CharField(max_length=100, description="??Key", index=True)
    heading = fields.CharField(max_length=300, null=True, description="????", index=True)
    heading_path = fields.CharField(max_length=1000, null=True, description="????")
    level = fields.IntField(default=0, description="????", index=True)
    start_line = fields.IntField(description="????", index=True)
    end_line = fields.IntField(description="????", index=True)
    text = fields.TextField(description="????")
    text_preview = fields.TextField(null=True, description="????")
    keywords = fields.JSONField(default=list, description="???")
    token_count = fields.IntField(default=0, description="??Token?")
    extra_metadata = fields.JSONField(default=dict, description="???")

    class Meta:
        table = "sk_document_section"
        unique_together = ("document_id", "section_key")


class SkillKnowDocumentLine(BaseModel, TimestampMixin):
    document_id = fields.BigIntField(description="??ID", index=True)
    line_no = fields.IntField(description="??", index=True)
    content = fields.TextField(description="???")

    class Meta:
        table = "sk_document_line"
        unique_together = ("document_id", "line_no")


class SkillKnowConversation(BaseModel, TimestampMixin):
    uuid = fields.CharField(max_length=36, unique=True, description="会话UUID", index=True)
    title = fields.CharField(max_length=200, null=True, description="会话标题", index=True)
    owner_id = fields.BigIntField(null=True, description="所有者ID", index=True)
    extra_metadata = fields.JSONField(default=dict, description="元数据")

    class Meta:
        table = "sk_conversation"


class SkillKnowMessage(BaseModel, TimestampMixin):
    uuid = fields.CharField(max_length=36, unique=True, description="消息UUID", index=True)
    conversation_id = fields.BigIntField(description="会话ID", index=True)
    role = fields.CharEnumField(SkillKnowMessageRole, description="消息角色", index=True)
    content = fields.TextField(description="消息内容")
    tool_calls = fields.JSONField(null=True, description="工具调用")
    timeline = fields.JSONField(default=list, description="时间线事件")
    latency_ms = fields.IntField(null=True, description="响应耗时")
    is_archived = fields.BooleanField(default=False, description="是否归档", index=True)
    extra_metadata = fields.JSONField(default=dict, description="元数据")

    class Meta:
        table = "sk_message"


class SkillKnowSystemConfig(BaseModel, TimestampMixin):
    key = fields.CharField(max_length=100, unique=True, description="配置Key", index=True)
    value = fields.JSONField(null=True, description="配置值")
    description = fields.TextField(null=True, description="描述")
    is_sensitive = fields.BooleanField(default=False, description="是否敏感")
    group = fields.CharField(max_length=50, default="general", description="分组", index=True)

    class Meta:
        table = "sk_system_config"


class SkillKnowUploadTask(BaseModel, TimestampMixin):
    uuid = fields.CharField(max_length=36, unique=True, description="任务UUID", index=True)
    status = fields.CharField(max_length=30, default="pending", description="任务状态", index=True)
    total = fields.IntField(default=0, description="总数")
    success_count = fields.IntField(default=0, description="成功数")
    failed_count = fields.IntField(default=0, description="失败数")
    result = fields.JSONField(default=dict, description="任务结果")
    error_message = fields.TextField(null=True, description="错误信息")

    class Meta:
        table = "sk_upload_task"


