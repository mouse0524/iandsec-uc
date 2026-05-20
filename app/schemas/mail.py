from pydantic import BaseModel, EmailStr, Field

from app.models.enums import RegisterType


class SendVerifyCodeIn(BaseModel):
    email: EmailStr = Field(..., description="邮箱")
    captcha_id: str = Field(..., description="验证码ID")
    captcha_code: str = Field(..., description="图形验证码")
    register_type: RegisterType | None = Field(default=None, description="注册类型")


class SendResetPasswordCodeIn(BaseModel):
    email: EmailStr = Field(..., description="邮箱")
    captcha_id: str = Field(..., description="验证码ID")
    captcha_code: str = Field(..., description="图形验证码")


class ResetPasswordByEmailIn(BaseModel):
    email: EmailStr = Field(..., description="邮箱")
    email_code: str = Field(..., description="邮箱验证码")
    new_password: str = Field(..., description="新密码")
