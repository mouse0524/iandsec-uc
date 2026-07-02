from datetime import datetime

from pydantic import BaseModel, Field


class ProjectProductPointIn(BaseModel):
    product_name: str = Field(..., description="使用产品")
    points: int = Field(default=0, description="点数")


class ProjectCreateIn(BaseModel):
    project_name: str = Field(..., description="项目名称")
    product_points: list[ProjectProductPointIn] = Field(default_factory=list, description="产品点数")
    region: str | None = Field(default=None, description="区域")
    agent_id: int | None = Field(default=None, description="所属代理商ID")
    server_version: str | None = Field(default=None, description="服务器版本")
    client_version: str | None = Field(default=None, description="客户端版本")
    start_time: datetime | None = Field(default=None, description="开始时间")
    end_time: datetime | None = Field(default=None, description="结束时间")
    maintenance_time: datetime | None = Field(default=None, description="维保时间")
    customer_contact: str | None = Field(default=None, description="客户侧对接人")
    customer_phone: str | None = Field(default=None, description="客户联系电话")
    customer_email: str | None = Field(default=None, description="客户联系邮箱")
    status: str | None = Field(default=None, description="项目状态")
    assignee_id: int | None = Field(default=None, description="负责人ID")
    remark: str | None = Field(default=None, description="备注")
    attachment_ids: list[int] = Field(default_factory=list, description="附件ID列表")


class ProjectUpdateIn(ProjectCreateIn):
    project_id: int = Field(..., description="项目ID")


class ProjectStatusIn(BaseModel):
    project_id: int = Field(..., description="项目ID")
    status: str = Field(..., description="项目状态")


class ProjectAssignIn(BaseModel):
    project_id: int = Field(..., description="项目ID")
    assignee_id: int | None = Field(default=None, description="负责人ID")


class ProjectActivityCreateIn(BaseModel):
    project_id: int = Field(..., description="项目ID")
    activity_type: str = Field(..., description="活动类型")
    title: str = Field(..., description="活动标题")
    content: str | None = Field(default=None, description="活动内容")
    status: str = Field(default="待处理", description="活动状态")
    operator_id: int | None = Field(default=None, description="处理人ID")
    started_at: datetime | None = Field(default=None, description="开始时间")
    finished_at: datetime | None = Field(default=None, description="完成时间")


class ProjectActivityUpdateIn(ProjectActivityCreateIn):
    activity_id: int = Field(..., description="活动ID")
