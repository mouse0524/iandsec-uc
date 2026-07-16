from datetime import date
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import IssueCustomFieldFormat, IssueRelationType


class IssueUpdateIn(BaseModel):
    issue_id: int = Field(..., description="Issue ID")
    changes: dict[str, Any] = Field(default_factory=dict, description="Issue字段变更")
    custom_values: dict[str, Any] = Field(default_factory=dict, description="自定义字段值")
    notes: str | None = Field(None, description="备注")
    private_notes: bool = Field(False, description="是否私有备注")


class IssueCreateIn(BaseModel):
    title: str = Field("", description="标题")
    description: str = Field("", description="描述")
    company_name: str | None = Field(None, description="项目名称")
    contact_name: str | None = Field(None, description="联系人")
    email: str | None = Field(None, description="邮箱")
    phone: str | None = Field(None, description="手机号")
    project_phase: str = Field("现网", description="项目阶段")
    issue_type: str | None = Field(None, description="Tracker名称")
    impact_scope: str = Field("全部", description="影响范围")
    category: str = Field("未分类", description="分类")
    issue_project_id: int | None = Field(None, description="项目ID")
    issue_tracker_id: int | None = Field(None, description="Tracker ID")
    issue_status_id: int | None = Field(None, description="状态ID")
    issue_priority_id: int | None = Field(None, description="优先级ID")
    issue_category_id: int | None = Field(None, description="分类ID")
    issue_fixed_version_id: int | None = Field(None, description="目标版本ID")
    parent_issue_id: int | None = Field(None, description="父Issue ID")
    root_issue_id: int | None = Field(None, description="根Issue ID")
    assigned_to_id: int | None = Field(None, description="指派人ID")
    start_date: date | None = Field(None, description="开始日期")
    due_date: date | None = Field(None, description="截止日期")
    done_ratio: int = Field(0, ge=0, le=100, description="完成率")
    estimated_hours: float | None = Field(None, ge=0, description="预估工时")
    is_private: bool = Field(False, description="是否私有")
    custom_values: dict[str, Any] = Field(default_factory=dict, description="自定义字段值")
    attachment_ids: list[int] = Field(default_factory=list, description="附件ID列表")
    notes: str | None = Field(None, description="创建备注")


class IssueWatcherIn(BaseModel):
    issue_id: int = Field(..., description="Issue ID")
    user_id: int | None = Field(None, description="用户ID")


class IssueRelationCreateIn(BaseModel):
    issue_id: int = Field(..., description="Issue ID")
    related_issue_id: int = Field(..., description="关联Issue ID")
    relation_type: IssueRelationType = Field(IssueRelationType.RELATES, description="关系类型")
    delay: int | None = Field(None, description="延迟天数")


class IssueTimeEntryCreateIn(BaseModel):
    issue_id: int = Field(..., description="Issue ID")
    hours: float = Field(..., gt=0, description="工时")
    comments: str | None = Field(None, description="备注")
    spent_on: date | None = Field(None, description="登记日期")
    activity_id: int | None = Field(None, description="活动ID")


class IssueQueryCreateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120, description="查询名称")
    filters: dict[str, Any] = Field(default_factory=dict, description="筛选条件")
    columns: list[str] = Field(default_factory=list, description="显示列")
    sort_criteria: list[Any] = Field(default_factory=list, description="排序规则")
    visibility: str = Field("private", description="可见性")
    project_id: int | None = Field(None, description="项目ID")

    @field_validator("visibility")
    @classmethod
    def validate_visibility(cls, value: str) -> str:
        value = str(value or "private").strip().lower()
        if value not in {"private", "public"}:
            raise ValueError("可见性仅支持 private/public")
        return value


class IssueQueryUpdateIn(IssueQueryCreateIn):
    query_id: int = Field(..., description="查询ID")


class IssueAdminTrackerSaveIn(BaseModel):
    id: int | None = Field(None, description="Tracker ID")
    name: str = Field(..., min_length=1, max_length=60, description="跟踪名称")
    description: str | None = Field(None, description="说明")
    position: int = Field(0, ge=0, description="排序")
    default_status_id: int | None = Field(None, description="默认状态ID")
    is_in_roadmap: bool = Field(True, description="是否进入路线图")
    copy_workflow_from_id: int | None = Field(None, description="复制工作流来源Tracker ID")
    is_active: bool = Field(True, description="是否启用")


class IssueAdminStatusSaveIn(BaseModel):
    id: int | None = Field(None, description="状态ID")
    name: str = Field(..., min_length=1, max_length=60, description="状态名称")
    position: int = Field(0, ge=0, description="排序")
    is_closed: bool = Field(False, description="是否关闭态")
    is_default: bool = Field(False, description="是否默认状态")
    active: bool = Field(True, description="是否启用")


class IssueAdminPrioritySaveIn(BaseModel):
    id: int | None = Field(None, description="优先级ID")
    name: str = Field(..., min_length=1, max_length=60, description="优先级名称")
    position: int = Field(0, ge=0, description="排序")
    is_default: bool = Field(False, description="是否默认优先级")
    active: bool = Field(True, description="是否启用")


class IssueAdminWorkflowSaveIn(BaseModel):
    id: int | None = Field(None, description="工作流ID")
    role_id: int = Field(..., description="角色ID")
    tracker_id: int = Field(..., description="Tracker ID")
    old_status_id: int = Field(..., description="原状态ID")
    new_status_id: int | None = Field(None, description="目标状态ID")
    new_status_ids: list[int] = Field(default_factory=list, description="目标状态ID列表")
    assignee_required: bool = Field(True, description="是否必须指派")
    author_allowed: bool = Field(True, description="提交人是否可执行")
    assignee_allowed: bool = Field(True, description="指派人是否可执行")

    @field_validator("new_status_ids")
    @classmethod
    def normalize_new_status_ids(cls, value: list[int]):
        result = []
        for item in value or []:
            status_id = int(item or 0)
            if status_id > 0 and status_id not in result:
                result.append(status_id)
        return result

    @model_validator(mode="after")
    def validate_target_statuses(self):
        if "new_status_ids" in self.model_fields_set and not self.new_status_ids:
            return self
        if not self.new_status_ids and self.new_status_id:
            self.new_status_ids = [self.new_status_id]
        if self.new_status_ids and self.new_status_id is None:
            self.new_status_id = self.new_status_ids[0]
        if not self.new_status_ids:
            raise ValueError("目标状态至少选择一项")
        return self


class IssueAdminCustomFieldSaveIn(BaseModel):
    id: int | None = Field(None, description="自定义字段ID")
    type: str = Field("issue", max_length=30, description="自定义字段类型")
    name: str = Field(..., min_length=1, max_length=120, description="字段名称")
    field_format: IssueCustomFieldFormat = Field(IssueCustomFieldFormat.STRING, description="字段格式")
    possible_values: list[str] = Field(default_factory=list, description="可选值")
    default_value: str | None = Field(None, description="默认值")
    is_required: bool = Field(False, description="是否必填")
    is_filter: bool = Field(False, description="是否可筛选")
    show_in_list: bool = Field(False, description="是否在列表显示")
    searchable: bool = Field(False, description="是否可搜索")
    multiple: bool = Field(False, description="是否多选")
    visible: bool = Field(True, description="是否可见")
    position: int = Field(0, ge=0, description="排序")
