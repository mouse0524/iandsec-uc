from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CredentialsSchema(BaseModel):
    username: str = Field(..., description="用户名称", example="admin")
    password: str = Field(..., description="密码", example="123456")
    captcha_id: str = Field(..., description="验证码ID")
    captcha_code: str = Field(..., description="验证码")


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
