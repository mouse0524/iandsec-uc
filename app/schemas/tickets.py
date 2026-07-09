from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.enums import TicketActionType, TicketStatus
from app.utils.company_name import validate_legal_company_name


class TicketCreate(BaseModel):
    company_name: str = Field(..., description="公司名称")
    contact_name: str = Field(..., description="联系人")
    email: EmailStr = Field(..., description="邮箱")
    phone: str = Field(..., description="手机号")
    project_phase: str = Field(..., description="项目阶段")
    issue_type: str | None = Field(default=None, description="跟踪")
    impact_scope: str | None = Field(default=None, description="影响范围")
    category: str = Field(..., description="问题分类")
    title: str = Field(..., description="问题标题")
    description: str = Field(..., description="问题描述")
    attachment_ids: list[int] = Field(default_factory=list, description="附件ID列表")
    captcha_id: str | None = Field(default=None, description="验证码ID")
    captcha_code: str | None = Field(default=None, description="验证码")
    turnstile_token: str | None = Field(default=None, description="Cloudflare Turnstile Token")

    @field_validator("company_name")
    @classmethod
    def validate_company_name(cls, value: str) -> str:
        return validate_legal_company_name(value)


class TicketReviewIn(BaseModel):
    ticket_id: int = Field(..., description="工单ID")
    approved: bool = Field(..., description="是否通过")
    comment: Optional[str] = Field(None, description="审核备注")
    tech_id: Optional[int] = Field(None, description="指派技术人员ID")


class TicketTechActionIn(BaseModel):
    ticket_id: int = Field(..., description="工单ID")
    action: TicketActionType = Field(..., description="技术动作")
    comment: Optional[str] = Field(None, description="处理备注")
    root_cause: Optional[str] = Field(None, description="问题根因")


class TicketAssignTechIn(BaseModel):
    ticket_id: int = Field(..., description="工单ID")
    tech_id: int = Field(..., description="新的技术处理人ID")
    comment: Optional[str] = Field(None, description="改派备注")


class TicketRedmineSyncIn(BaseModel):
    ticket_id: int = Field(..., description="工单ID")
    note: Optional[str] = Field(None, description="同步备注")
    project_id: Optional[str] = Field(None, description="Redmine Project ID")
    tracker_id: Optional[int] = Field(None, description="Redmine Tracker ID")
    priority_id: Optional[int] = Field(None, description="Redmine Priority ID")
    assigned_to_id: Optional[int] = Field(None, description="Redmine Assignee ID")
    project_phase: Optional[str] = Field(None, description="Redmine project phase custom field value")
    os_value: Optional[str] = Field(None, description="Redmine OS custom field value")


class TicketCloseIn(BaseModel):
    ticket_id: int = Field(..., description="工单ID")
    comment: Optional[str] = Field(None, description="关闭备注")


class TicketFieldVerificationIn(BaseModel):
    ticket_id: int = Field(..., description="工单ID")
    approved: bool = Field(..., description="现场验证是否通过")
    comment: Optional[str] = Field(None, description="现场验证备注")


class TicketResubmitIn(BaseModel):
    ticket_id: int = Field(..., description="工单ID")
    description: Optional[str] = Field(None, description="补充描述")
    attachment_ids: list[int] = Field(default_factory=list, description="新增附件ID")
    captcha_id: str | None = Field(default=None, description="验证码ID")
    captcha_code: str | None = Field(default=None, description="验证码")
    turnstile_token: str | None = Field(default=None, description="Cloudflare Turnstile Token")


class TicketUpdateIn(BaseModel):
    ticket_id: int = Field(..., description="工单ID")
    company_name: str = Field(..., description="公司名称")
    contact_name: str = Field(..., description="联系人")
    email: EmailStr = Field(..., description="邮箱")
    phone: str = Field(..., description="手机号")
    project_phase: str = Field(..., description="项目阶段")
    issue_type: str | None = Field(default=None, description="跟踪")
    impact_scope: str | None = Field(default=None, description="影响范围")
    category: str = Field(..., description="问题分类")
    title: str = Field(..., description="问题标题")
    description: str = Field(..., description="问题描述")
    attachment_ids: list[int] = Field(default_factory=list, description="附件ID列表")
    captcha_id: str | None = Field(default=None, description="验证码ID")
    captcha_code: str | None = Field(default=None, description="验证码")
    turnstile_token: str | None = Field(default=None, description="Cloudflare Turnstile Token")

    @field_validator("company_name")
    @classmethod
    def validate_company_name(cls, value: str) -> str:
        return validate_legal_company_name(value)


class TicketUploadOut(BaseModel):
    attachment_id: int
    origin_name: str
    file_path: str
    file_size: int


class TicketListQuery(BaseModel):
    page: int = 1
    page_size: int = 10
    status: Optional[TicketStatus] = None
    project_phase: Optional[str] = None
    issue_type: Optional[str] = None
    impact_scope: Optional[str] = None
    category: Optional[str] = None
    title: Optional[str] = None
    submitter_id: Optional[int] = None


class TicketActionLogOut(BaseModel):
    id: int
    ticket_id: int
    action: TicketActionType
    from_status: Optional[TicketStatus]
    to_status: TicketStatus
    operator_id: int
    comment: Optional[str]
    created_at: datetime
