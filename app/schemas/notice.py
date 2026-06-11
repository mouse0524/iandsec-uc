from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class NoticeCreateIn(BaseModel):
    title: str | None = Field(default=None, max_length=100, description="通知标题")
    content_html: str = Field(..., description="通知内容HTML")
    target_type: str = Field(..., description="发送范围：all/roles/users")
    target_role_ids: list[int] = Field(default_factory=list, description="角色ID列表")
    target_user_ids: list[int] = Field(default_factory=list, description="用户ID列表")
    delivery_channels: list[str] = Field(default_factory=lambda: ["site"], description="投递渠道：site/email")

    @field_validator("target_type")
    @classmethod
    def validate_target_type(cls, value: str):
        if value not in {"all", "roles", "users"}:
            raise ValueError("target_type 仅支持 all/roles/users")
        return value

    @field_validator("content_html")
    @classmethod
    def validate_content_html(cls, value: str):
        text = str(value or "").strip()
        if not text:
            raise ValueError("通知内容不能为空")
        plain_text_len = len("".join(ch for ch in text if ch != "<" and ch != ">"))
        if plain_text_len > 2000:
            raise ValueError("通知内容纯文本长度不能超过2000")
        return value

    @field_validator("delivery_channels")
    @classmethod
    def validate_delivery_channels(cls, value: list[str]):
        channels = [str(item or "").strip() for item in (value or [])]
        channels = [item for item in channels if item]
        invalid = [item for item in channels if item not in {"site", "email"}]
        if invalid:
            raise ValueError("delivery_channels 仅支持 site/email")
        if not channels:
            raise ValueError("请至少选择一种通知方式")
        return list(dict.fromkeys(channels))


class NoticeReadIn(BaseModel):
    notice_id: int = Field(..., description="通知ID")


class NoticeListQuery(BaseModel):
    page: int = 1
    page_size: int = 10


class NoticeInboxItemOut(BaseModel):
    notice_id: int
    title: str | None = None
    content_html: str
    is_read: bool
    read_at: datetime | None = None
    delivered_at: datetime
    created_at: datetime
