from pydantic import BaseModel, Field, field_validator

from app.models.enums import PartnerLevel


class BaseDept(BaseModel):
    name: str = Field(..., description="部门名称", example="研发中心")
    desc: str = Field("", description="备注", example="研发中心")
    channel_level: PartnerLevel | None = Field(default=None, description="代理商级别")
    tech_ids: list[int] = Field(default_factory=list, description="关联技术ID列表")
    order: int = Field(0, description="排序")
    parent_id: int = Field(0, description="父部门ID")

    @field_validator("parent_id", mode="before")
    @classmethod
    def empty_parent_is_root(cls, value):
        return 0 if value is None else value


class DeptCreate(BaseDept): ...


class DeptUpdate(BaseDept):
    id: int

    def update_dict(self):
        return self.model_dump(exclude_unset=True, exclude={"id"})
