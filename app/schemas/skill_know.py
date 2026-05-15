from datetime import datetime
from typing import Any

import re

from pydantic import BaseModel, Field, field_validator

from app.models.enums import (
    SkillKnowDocumentStatus,
    SkillKnowMessageRole,
)


class SkillKnowFolderIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    parent_id: int | None = None
    sort_order: int = 0


class SkillKnowFolderUpdate(BaseModel):
    folder_id: int
    name: str | None = None
    description: str | None = None
    parent_id: int | None = None
    sort_order: int | None = None


class SkillKnowDocumentUpdate(BaseModel):
    document_id: int
    title: str | None = None
    description: str | None = None
    abstract: str | None = None
    overview: str | None = None
    content: str | None = None
    category: str | None = None
    tags: list[str] | None = None
    folder_id: int | None = None


class SkillKnowChunkUploadInitIn(BaseModel):
    filename: str = Field(..., min_length=1)
    title: str | None = None
    folder_id: int | None = None
    file_size: int = Field(..., gt=0)
    total_chunks: int = Field(..., ge=1)


class SkillKnowChunkUploadCompleteIn(SkillKnowChunkUploadInitIn):
    upload_id: str = Field(..., min_length=1)


class SkillKnowMoveIn(BaseModel):
    target_id: int
    folder_id: int | None = None


class SkillKnowQuickSetupIn(BaseModel):
    llm_api_key: str | None = None
    llm_chat_api_key: str | None = None
    llm_chat_provider: str = "openai"
    llm_chat_base_url: str = "https://api.openai.com/v1"
    llm_chat_model: str = "gpt-4o-mini"

    @field_validator("llm_chat_model")
    @classmethod
    def validate_chat_models(cls, value: str) -> str:
        models = [item.strip() for item in re.split(r"[\n,;，；]+", str(value or "")) if item.strip()]
        if not models:
            raise ValueError("至少配置一个 Chat Model")
        if len(models) > 5:
            raise ValueError("Chat Model 最多配置 5 个")
        return value


class SkillKnowTestConnectionIn(BaseModel):
    llm_api_key: str | None = None
    llm_chat_api_key: str | None = None
    llm_chat_provider: str = "openai"
    llm_chat_base_url: str = "https://api.openai.com/v1"
    llm_chat_model: str = "gpt-4o-mini"

    @field_validator("llm_chat_model")
    @classmethod
    def validate_chat_models(cls, value: str) -> str:
        return SkillKnowQuickSetupIn.validate_chat_models(value)


class SkillKnowChatIn(BaseModel):
    message: str = Field(..., min_length=1)
    conversation_id: int | None = None


class SkillKnowMessageFeedbackIn(BaseModel):
    message_id: int
    rating: str = Field(..., pattern="^(up|down)$")
    reason: str | None = None
    note: str | None = None


class SkillKnowGoldenCaseIn(BaseModel):
    id: str | None = None
    question: str = Field(..., min_length=1)
    expected_document_id: int | None = None
    expected_section_id: int | None = None
    expected_heading_contains: str | None = None
    enabled: bool = True


class SkillKnowFolderOut(BaseModel):
    id: int
    uuid: str
    name: str
    description: str | None
    parent_id: int | None
    sort_order: int
    is_system: bool
    created_at: datetime | str | None = None
    updated_at: datetime | str | None = None
    children: list["SkillKnowFolderOut"] = Field(default_factory=list)


class SkillKnowDocumentOut(BaseModel):
    id: int
    uuid: str
    uri: str | None
    title: str
    description: str | None
    filename: str
    file_path: str
    file_size: int
    file_type: str
    abstract: str | None
    overview: str | None
    content: str | None
    content_hash: str | None
    status: SkillKnowDocumentStatus
    error_message: str | None
    category: str | None
    tags: list[str]
    folder_id: int | None
    extra_metadata: dict[str, Any]
    created_at: datetime | str | None = None
    updated_at: datetime | str | None = None


class SkillKnowMessageOut(BaseModel):
    id: int
    uuid: str
    conversation_id: int
    role: SkillKnowMessageRole
    content: str
    tool_calls: list | None
    timeline: list
    latency_ms: int | None
    extra_metadata: dict[str, Any]
    created_at: datetime | str | None = None


class SkillKnowConversationOut(BaseModel):
    id: int
    uuid: str
    title: str | None
    extra_metadata: dict[str, Any]
    created_at: datetime | str | None = None
    updated_at: datetime | str | None = None
    messages: list[SkillKnowMessageOut] = Field(default_factory=list)


SkillKnowFolderOut.model_rebuild()
