from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.enums import RegisterType


class PartnerRegisterIn(BaseModel):
    register_type: RegisterType = Field(default=RegisterType.CHANNEL, description="注册类型")
    company_name: str = Field(..., description="公司名称")
    contact_name: str = Field(..., description="联系人")
    email: EmailStr = Field(..., description="邮箱")
    phone: str = Field(..., description="手机号")
    hardware_id: str | None = Field(default=None, description="产品硬件ID")
    password: str = Field(..., min_length=6, max_length=32, description="密码")
    email_code: str = Field(..., description="邮箱验证码")

    @field_validator("company_name")
    @classmethod
    def validate_company_name(cls, value: str) -> str:
        name = str(value or "").strip()
        if not name:
            raise ValueError("请输入公司名称")
        if "公司" not in name:
            raise ValueError("公司名称必须包含“公司”，请填写完整公司名称")
        return name


class UserRegisterIn(PartnerRegisterIn):
    hardware_id: str = Field(..., min_length=1, description="设备机器码")


class PartnerReviewIn(BaseModel):
    id: int = Field(..., description="申请ID")
    approved: bool = Field(..., description="是否通过")
    comment: Optional[str] = Field(None, description="审核备注")
