from tortoise import fields

from app.schemas.menus import MenuType

from .base import BaseModel, TimestampMixin
from .enums import (
    IssueCustomFieldFormat,
    IssueRelationType,
    IssueVersionSharing,
    IssueVersionStatus,
    IssueWorkflowFieldRule,
    MethodType,
    PartnerRegisterStatus,
    PartnerLevel,
    RegisterType,
    TicketActionType,
    TicketStatus,
)


class User(BaseModel, TimestampMixin):
    username = fields.CharField(max_length=255, unique=True, description="用户名称", index=True)
    alias = fields.CharField(max_length=30, null=True, description="用户姓名", index=True)
    company_name = fields.CharField(max_length=120, null=True, description="公司名称", index=True)
    channel_level = fields.CharEnumField(PartnerLevel, null=True, description="代理商级别", index=True)
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
    channel_level = fields.CharEnumField(PartnerLevel, null=True, description="代理商级别", index=True)
    tech_ids = fields.JSONField(default=list, description="关联技术ID列表")
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
    issue_project_id = fields.BigIntField(null=True, description="Issue项目ID", index=True)
    issue_tracker_id = fields.BigIntField(null=True, description="Issue跟踪ID", index=True)
    issue_status_id = fields.BigIntField(null=True, description="Issue状态ID", index=True)
    issue_priority_id = fields.BigIntField(null=True, description="Issue优先级ID", index=True)
    issue_category_id = fields.BigIntField(null=True, description="Issue分类ID", index=True)
    issue_fixed_version_id = fields.BigIntField(null=True, description="Issue目标版本ID", index=True)
    parent_issue_id = fields.BigIntField(null=True, description="父Issue ID", index=True)
    root_issue_id = fields.BigIntField(null=True, description="根Issue ID", index=True)
    assigned_to_id = fields.BigIntField(null=True, description="Issue指派人ID", index=True)
    start_date = fields.DateField(null=True, description="开始日期", index=True)
    due_date = fields.DateField(null=True, description="截止日期", index=True)
    done_ratio = fields.IntField(default=0, description="完成率")
    estimated_hours = fields.FloatField(null=True, description="预估工时")
    closed_at = fields.DatetimeField(null=True, description="关闭时间", index=True)
    is_private = fields.BooleanField(default=False, description="是否私有", index=True)
    lock_version = fields.IntField(default=0, description="乐观锁版本")

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


class ProjectMember(BaseModel, TimestampMixin):
    project_id = fields.BigIntField(description="项目ID", index=True)
    user_id = fields.BigIntField(description="用户ID", index=True)
    role_id = fields.BigIntField(description="角色ID", index=True)

    class Meta:
        table = "project_member"
        unique_together = ("project_id", "user_id", "role_id")


class IssueTracker(BaseModel, TimestampMixin):
    name = fields.CharField(max_length=60, unique=True, description="跟踪名称", index=True)
    description = fields.TextField(null=True, description="说明")
    position = fields.IntField(default=0, description="排序", index=True)
    default_status_id = fields.BigIntField(null=True, description="默认状态ID", index=True)
    is_in_roadmap = fields.BooleanField(default=True, description="是否进入路线图", index=True)
    copy_workflow_from_id = fields.BigIntField(null=True, description="复制工作流来源Tracker ID")
    is_active = fields.BooleanField(default=True, description="是否启用", index=True)

    class Meta:
        table = "issue_tracker"


class IssueStatus(BaseModel, TimestampMixin):
    name = fields.CharField(max_length=60, unique=True, description="状态名称", index=True)
    position = fields.IntField(default=0, description="排序", index=True)
    is_closed = fields.BooleanField(default=False, description="是否关闭态", index=True)
    is_default = fields.BooleanField(default=False, description="是否默认状态", index=True)
    active = fields.BooleanField(default=True, description="是否启用", index=True)

    class Meta:
        table = "issue_status"


class IssuePriority(BaseModel, TimestampMixin):
    name = fields.CharField(max_length=60, unique=True, description="优先级名称", index=True)
    position = fields.IntField(default=0, description="排序", index=True)
    is_default = fields.BooleanField(default=False, description="是否默认优先级", index=True)
    active = fields.BooleanField(default=True, description="是否启用", index=True)

    class Meta:
        table = "issue_priority"


class IssueCategory(BaseModel, TimestampMixin):
    project_id = fields.BigIntField(description="项目ID", index=True)
    name = fields.CharField(max_length=120, description="分类名称", index=True)
    assigned_to_id = fields.BigIntField(null=True, description="默认指派人ID", index=True)

    class Meta:
        table = "issue_category"
        unique_together = ("project_id", "name")


class IssueVersion(BaseModel, TimestampMixin):
    project_id = fields.BigIntField(description="项目ID", index=True)
    name = fields.CharField(max_length=120, description="版本名称", index=True)
    description = fields.TextField(null=True, description="说明")
    status = fields.CharEnumField(IssueVersionStatus, max_length=20, default=IssueVersionStatus.OPEN, index=True)
    sharing = fields.CharEnumField(IssueVersionSharing, max_length=20, default=IssueVersionSharing.NONE, index=True)
    effective_date = fields.DateField(null=True, description="计划日期", index=True)

    class Meta:
        table = "issue_version"
        unique_together = ("project_id", "name")


class IssueCustomField(BaseModel, TimestampMixin):
    type = fields.CharField(max_length=30, default="issue", description="自定义字段类型", index=True)
    name = fields.CharField(max_length=120, description="字段名称", index=True)
    field_format = fields.CharEnumField(
        IssueCustomFieldFormat,
        max_length=20,
        default=IssueCustomFieldFormat.STRING,
        description="字段格式",
        index=True,
    )
    possible_values = fields.JSONField(default=list, description="可选值")
    default_value = fields.TextField(null=True, description="默认值")
    is_required = fields.BooleanField(default=False, description="是否必填", index=True)
    is_filter = fields.BooleanField(default=False, description="是否可筛选", index=True)
    searchable = fields.BooleanField(default=False, description="是否可搜索", index=True)
    multiple = fields.BooleanField(default=False, description="是否多选")
    visible = fields.BooleanField(default=True, description="是否可见", index=True)
    position = fields.IntField(default=0, description="排序", index=True)

    class Meta:
        table = "issue_custom_field"


class IssueCustomFieldBinding(BaseModel, TimestampMixin):
    custom_field_id = fields.BigIntField(description="自定义字段ID", index=True)
    tracker_id = fields.BigIntField(null=True, description="Tracker ID", index=True)
    project_id = fields.BigIntField(null=True, description="项目ID", index=True)

    class Meta:
        table = "issue_custom_field_binding"


class IssueCustomValue(BaseModel, TimestampMixin):
    customized_type = fields.CharField(max_length=30, default="Issue", description="归属类型", index=True)
    customized_id = fields.BigIntField(description="归属ID", index=True)
    custom_field_id = fields.BigIntField(description="自定义字段ID", index=True)
    value = fields.TextField(null=True, description="字段值")

    class Meta:
        table = "issue_custom_value"


class IssueWorkflowTransition(BaseModel, TimestampMixin):
    role_id = fields.BigIntField(description="角色ID", index=True)
    tracker_id = fields.BigIntField(description="Tracker ID", index=True)
    old_status_id = fields.BigIntField(description="原状态ID", index=True)
    new_status_id = fields.BigIntField(description="目标状态ID", index=True)
    assignee_required = fields.BooleanField(default=True, description="是否必须指派")
    author_allowed = fields.BooleanField(default=True, description="提交人是否可执行")
    assignee_allowed = fields.BooleanField(default=True, description="指派人是否可执行")

    class Meta:
        table = "issue_workflow_transition"
        unique_together = ("role_id", "tracker_id", "old_status_id", "new_status_id")


class IssueWorkflowPermission(BaseModel, TimestampMixin):
    role_id = fields.BigIntField(description="角色ID", index=True)
    tracker_id = fields.BigIntField(description="Tracker ID", index=True)
    old_status_id = fields.BigIntField(description="状态ID", index=True)
    field_name = fields.CharField(max_length=120, description="字段名", index=True)
    rule = fields.CharEnumField(IssueWorkflowFieldRule, max_length=20, description="字段规则", index=True)

    class Meta:
        table = "issue_workflow_permission"
        unique_together = ("role_id", "tracker_id", "old_status_id", "field_name", "rule")


class IssueWatcher(BaseModel, TimestampMixin):
    watchable_type = fields.CharField(max_length=30, default="Issue", description="关注对象类型", index=True)
    watchable_id = fields.BigIntField(description="关注对象ID", index=True)
    user_id = fields.BigIntField(description="用户ID", index=True)

    class Meta:
        table = "issue_watcher"
        unique_together = ("watchable_type", "watchable_id", "user_id")


class IssueRelation(BaseModel, TimestampMixin):
    issue_from_id = fields.BigIntField(description="来源Issue ID", index=True)
    issue_to_id = fields.BigIntField(description="目标Issue ID", index=True)
    relation_type = fields.CharEnumField(IssueRelationType, max_length=20, description="关系类型", index=True)
    delay = fields.IntField(null=True, description="延迟天数")

    class Meta:
        table = "issue_relation"
        unique_together = ("issue_from_id", "issue_to_id", "relation_type")


class IssueTimeEntry(BaseModel, TimestampMixin):
    project_id = fields.BigIntField(description="项目ID", index=True)
    issue_id = fields.BigIntField(null=True, description="Issue ID", index=True)
    user_id = fields.BigIntField(description="用户ID", index=True)
    activity_id = fields.BigIntField(null=True, description="活动ID", index=True)
    hours = fields.FloatField(description="工时")
    comments = fields.CharField(max_length=255, null=True, description="备注")
    spent_on = fields.DateField(description="登记日期", index=True)

    class Meta:
        table = "issue_time_entry"


class IssueJournal(BaseModel, TimestampMixin):
    journalized_type = fields.CharField(max_length=30, default="Issue", description="记录对象类型", index=True)
    journalized_id = fields.BigIntField(description="记录对象ID", index=True)
    user_id = fields.BigIntField(description="用户ID", index=True)
    notes = fields.TextField(null=True, description="备注")
    private_notes = fields.BooleanField(default=False, description="是否私有备注", index=True)

    class Meta:
        table = "issue_journal"


class IssueJournalDetail(BaseModel, TimestampMixin):
    journal_id = fields.BigIntField(description="Journal ID", index=True)
    property = fields.CharField(max_length=30, default="attr", description="属性类型", index=True)
    prop_key = fields.CharField(max_length=120, description="属性Key", index=True)
    old_value = fields.TextField(null=True, description="旧值")
    value = fields.TextField(null=True, description="新值")

    class Meta:
        table = "issue_journal_detail"


class IssueQuery(BaseModel, TimestampMixin):
    name = fields.CharField(max_length=120, description="查询名称", index=True)
    user_id = fields.BigIntField(null=True, description="用户ID", index=True)
    project_id = fields.BigIntField(null=True, description="项目ID", index=True)
    visibility = fields.CharField(max_length=20, default="private", description="可见性", index=True)
    filters = fields.JSONField(default=dict, description="筛选条件")
    columns = fields.JSONField(default=list, description="显示列")
    sort_criteria = fields.JSONField(default=list, description="排序规则")

    class Meta:
        table = "issue_query"


class Project(BaseModel, TimestampMixin):
    project_name = fields.CharField(max_length=120, description="项目名称", index=True)
    product_points = fields.JSONField(default=list, description="产品点数")
    region = fields.CharField(max_length=30, null=True, description="区域", index=True)
    agent_id = fields.BigIntField(null=True, description="所属代理商ID", index=True)
    server_version = fields.CharField(max_length=80, null=True, description="服务器版本")
    client_version = fields.CharField(max_length=80, null=True, description="客户端版本")
    start_time = fields.DatetimeField(null=True, description="开始时间")
    end_time = fields.DatetimeField(null=True, description="结束时间")
    maintenance_time = fields.DatetimeField(null=True, description="维保时间")
    customer_contact = fields.CharField(max_length=60, null=True, description="客户侧对接人")
    customer_phone = fields.CharField(max_length=20, null=True, description="客户联系电话")
    customer_email = fields.CharField(max_length=255, null=True, description="客户联系邮箱")
    status = fields.CharField(max_length=30, description="项目状态", index=True)
    assignee_id = fields.BigIntField(null=True, description="负责人ID", index=True)
    assigned_by = fields.BigIntField(null=True, description="指派人ID", index=True)
    assigned_at = fields.DatetimeField(null=True, description="指派时间")
    created_by = fields.BigIntField(description="创建人ID", index=True)
    remark = fields.TextField(null=True, description="备注")

    class Meta:
        table = "project"


class ProjectAttachment(BaseModel, TimestampMixin):
    project_id = fields.BigIntField(null=True, description="项目ID", index=True)
    origin_name = fields.CharField(max_length=255, description="原始文件名")
    file_path = fields.CharField(max_length=500, description="文件相对路径")
    file_size = fields.BigIntField(default=0, description="文件大小")
    mime_type = fields.CharField(max_length=100, default="application/octet-stream", description="MIME类型")
    uploader_id = fields.BigIntField(description="上传人ID", index=True)

    class Meta:
        table = "project_attachment"


class ProjectActivity(BaseModel, TimestampMixin):
    project_id = fields.BigIntField(description="项目ID", index=True)
    activity_type = fields.CharField(max_length=50, description="活动类型", index=True)
    title = fields.CharField(max_length=200, description="活动标题", index=True)
    content = fields.TextField(null=True, description="活动内容")
    status = fields.CharField(max_length=30, default="待处理", description="活动状态", index=True)
    operator_id = fields.BigIntField(null=True, description="处理人ID", index=True)
    started_at = fields.DatetimeField(null=True, description="开始时间")
    finished_at = fields.DatetimeField(null=True, description="完成时间")
    created_by = fields.BigIntField(description="创建人ID", index=True)

    class Meta:
        table = "project_activity"


class WikiSource(BaseModel, TimestampMixin):
    title = fields.CharField(max_length=200, description="Wiki source title", index=True)
    filename = fields.CharField(max_length=255, description="Original filename")
    file_path = fields.CharField(max_length=500, description="Raw file path")
    file_type = fields.CharField(max_length=20, description="File extension", index=True)
    file_size = fields.BigIntField(default=0, description="File size")
    content_hash = fields.CharField(max_length=64, description="SHA256 content hash", index=True)
    markdown_path = fields.CharField(max_length=500, null=True, description="Markdown file path")
    status = fields.CharField(max_length=20, default="pending", description="Import status", index=True)
    error_message = fields.TextField(null=True, description="Import error")
    created_by = fields.BigIntField(description="Uploader user id", index=True)

    class Meta:
        table = "wiki_source"


class WikiPage(BaseModel, TimestampMixin):
    path = fields.CharField(max_length=255, unique=True, description="Stable wiki path", index=True)
    title = fields.CharField(max_length=200, description="Wiki page title", index=True)
    page_type = fields.CharField(max_length=30, default="source", description="Page type", index=True)
    content = fields.TextField(description="Markdown content")
    source_id = fields.BigIntField(null=True, description="Source id", index=True)
    summary = fields.TextField(null=True, description="Page summary")
    content_hash = fields.CharField(max_length=64, description="Content hash", index=True)

    class Meta:
        table = "wiki_page"


class WikiLink(BaseModel, TimestampMixin):
    from_page_id = fields.BigIntField(description="From page id", index=True)
    to_page_id = fields.BigIntField(description="To page id", index=True)
    link_text = fields.CharField(max_length=200, description="Link text")

    class Meta:
        table = "wiki_link"


class WikiIngestJob(BaseModel, TimestampMixin):
    source_id = fields.BigIntField(description="Source id", index=True)
    status = fields.CharField(max_length=20, default="pending", description="Job status", index=True)
    stage = fields.CharField(max_length=40, default="created", description="Current stage", index=True)
    error_message = fields.TextField(null=True, description="Job error")

    class Meta:
        table = "wiki_ingest_job"


class WikiLearningCandidate(BaseModel, TimestampMixin):
    question = fields.TextField(description="User question")
    answer = fields.TextField(null=True, description="Answer text")
    evidence_page_ids = fields.JSONField(default=list, description="Evidence wiki page ids")
    reason = fields.CharField(max_length=80, description="Candidate reason", index=True)
    proposed_page_path = fields.CharField(max_length=255, null=True, description="Proposed page path", index=True)
    proposed_content = fields.TextField(null=True, description="Proposed markdown")
    status = fields.CharField(max_length=20, default="pending", description="Review status", index=True)
    reviewed_by = fields.BigIntField(null=True, description="Reviewer user id", index=True)

    class Meta:
        table = "wiki_learning_candidate"


class WikiConversation(BaseModel, TimestampMixin):
    title = fields.CharField(max_length=200, description="Wiki conversation title", index=True)
    owner_id = fields.BigIntField(description="Owner user id", index=True)

    class Meta:
        table = "wiki_conversation"


class WikiMessage(BaseModel, TimestampMixin):
    conversation_id = fields.BigIntField(description="Wiki conversation id", index=True)
    owner_id = fields.BigIntField(description="Owner user id", index=True)
    role = fields.CharField(max_length=20, description="Message role", index=True)
    content = fields.TextField(description="Message content")
    citations = fields.JSONField(default=list, description="Wiki citations")
    archive_path = fields.CharField(max_length=255, null=True, description="Archived query path")

    class Meta:
        table = "wiki_message"


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
    invite_code = fields.CharField(max_length=32, null=True, description="邀请码", index=True)

    class Meta:
        table = "partner_registration"


class PartnerInvite(BaseModel, TimestampMixin):
    code = fields.CharField(max_length=32, unique=True, description="邀请码", index=True)
    created_by = fields.BigIntField(description="创建技术ID", index=True)
    used_by = fields.BigIntField(null=True, description="使用注册申请ID", index=True)
    used_at = fields.DatetimeField(null=True, description="使用时间", index=True)

    class Meta:
        table = "partner_invite"


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


class WebDavDownloadLog(BaseModel, TimestampMixin):
    download_type = fields.CharField(max_length=20, description="下载类型", index=True)
    file_path = fields.CharField(max_length=1000, description="文件路径")
    file_name = fields.CharField(max_length=255, null=True, description="文件名")
    share_code = fields.CharField(max_length=32, null=True, description="分享码", index=True)
    downloader_id = fields.BigIntField(null=True, description="下载者ID", index=True)
    downloader_name = fields.CharField(max_length=120, null=True, description="下载者")
    source_ip = fields.CharField(max_length=64, null=True, description="来源IP", index=True)
    user_agent = fields.CharField(max_length=500, null=True, description="User-Agent")
    referer = fields.CharField(max_length=500, null=True, description="来源页面")

    class Meta:
        table = "webdav_download_log"


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
    delivery_channels = fields.JSONField(default=list, description="投递渠道")
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
