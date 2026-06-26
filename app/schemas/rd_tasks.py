from pydantic import BaseModel, Field

from app.models.enums import RdTaskStatus, RdTaskType


class RdTaskCreateFromTicketIn(BaseModel):
    ticket_id: int = Field(..., description="工单ID")
    task_type: RdTaskType = Field(..., description="任务类型")
    title: str | None = Field(default=None, description="任务标题")
    description: str | None = Field(default=None, description="任务描述")
    priority: str = Field(default="normal", description="优先级")
    product_owner_id: int | None = Field(default=None, description="产品负责人ID")
    dev_owner_id: int | None = Field(default=None, description="研发负责人ID")
    test_owner_id: int | None = Field(default=None, description="测试负责人ID")
    planned_version: str | None = Field(default=None, description="计划版本")


class RdTaskLinkTicketIn(BaseModel):
    task_id: int = Field(..., description="产研任务ID")
    ticket_id: int = Field(..., description="工单ID")


class RdTaskTransitionIn(BaseModel):
    task_id: int = Field(..., description="产研任务ID")
    action: str = Field(..., description="流转动作")
    comment: str | None = Field(default=None, description="备注")


class RdTaskListQuery(BaseModel):
    page: int = 1
    page_size: int = 10
    status: RdTaskStatus | None = None
    task_type: RdTaskType | None = None
    keyword: str | None = None
    owner_id: int | None = None
