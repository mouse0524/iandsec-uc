from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CredentialsSchema(BaseModel):
    username: str = Field(..., description="用户名称", example="admin")
    password: str = Field(..., description="密码", example="123456")
    captcha_id: str = Field(..., description="验证码ID")
    captcha_code: str = Field(..., description="验证码")
    remember_me: bool = Field(default=False, description="是否保持登录状态")


class JWTOut(BaseModel):
    access_token: str
    username: str


class JWTPayload(BaseModel):
    user_id: int
    username: str
    is_superuser: bool
    iss: str
    aud: str
    iat: datetime
    jti: UUID
    token_version: int = 0
    exp: datetime
