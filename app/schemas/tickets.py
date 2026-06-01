from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import TicketActionType, TicketStatus


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
    captcha_id: str = Field(..., description="验证码ID")
    captcha_code: str = Field(..., description="验证码")


class TicketReviewIn(BaseModel):
    ticket_id: int = Field(..., description="工单ID")
    approved: bool = Field(..., description="是否通过")
    comment: Optional[str] = Field(None, description="审核备注")
    tech_id: Optional[int] = Field(None, description="指派技术人员ID（审核通过时必填）")


class TicketTechActionIn(BaseModel):
    ticket_id: int = Field(..., description="工单ID")
    action: TicketActionType = Field(..., description="技术动作")
    comment: Optional[str] = Field(None, description="处理备注")
    root_cause: Optional[str] = Field(None, description="问题根因")


class TicketAssignTechIn(BaseModel):
    ticket_id: int = Field(..., description="工单ID")
    tech_id: int = Field(..., description="新的技术处理人ID")
    comment: Optional[str] = Field(None, description="改派备注")


class TicketResubmitIn(BaseModel):
    ticket_id: int = Field(..., description="工单ID")
    description: Optional[str] = Field(None, description="补充描述")
    attachment_ids: list[int] = Field(default_factory=list, description="新增附件ID")
    captcha_id: str = Field(..., description="验证码ID")
    captcha_code: str = Field(..., description="验证码")


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
    attachment_ids: list[int] = Field(default_factory=list, description="新增附件ID列表")
    captcha_id: str = Field(..., description="验证码ID")
    captcha_code: str = Field(..., description="验证码")


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
