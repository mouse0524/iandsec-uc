from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import (
    SkillKnowDocumentStatus,
    SkillKnowLearningStatus,
    SkillKnowMessageRole,
    SkillKnowPromptCategory,
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
    category: str | None = None
    tags: list[str] | None = None
    folder_id: int | None = None


class SkillKnowMoveIn(BaseModel):
    target_id: int
    folder_id: int | None = None


class SkillKnowPromptUpdate(BaseModel):
    content: str | None = None
    is_active: bool | None = None


class SkillKnowQuickSetupIn(BaseModel):
    llm_api_key: str | None = None
    llm_base_url: str = "https://api.openai.com/v1"
    llm_chat_model: str = "gpt-4o-mini"
    llm_embedding_model: str = "text-embedding-3-small"
    retrieval_top_k: int = Field(default=8, ge=1, le=30)
    retrieval_score_threshold: float = Field(default=0.25, ge=0.0, le=1.0)
    retrieval_max_context_chars: int = Field(default=12000, ge=2000, le=50000)
    chunk_size: int = Field(default=1400, ge=300, le=5000)
    chunk_overlap: int = Field(default=150, ge=0, le=1000)


class SkillKnowTestConnectionIn(BaseModel):
    llm_api_key: str | None = None
    llm_base_url: str = "https://api.openai.com/v1"
    llm_chat_model: str = "gpt-4o-mini"
    llm_embedding_model: str = "text-embedding-3-small"


class SkillKnowChatIn(BaseModel):
    message: str = Field(..., min_length=1)
    conversation_id: int | None = None


class SkillKnowMessageFeedbackIn(BaseModel):
    message_id: int
    rating: int | None = Field(default=None, ge=1, le=5)
    is_helpful: bool | None = None
    reason: str | None = None
    correct_answer: str | None = None


class SkillKnowLearningCandidateIn(BaseModel):
    question: str = Field(..., min_length=1)
    assistant_answer: str | None = None
    feedback_reason: str | None = None
    correct_answer: str | None = None
    candidate_markdown: str | None = None


class SkillKnowLearningReviewIn(BaseModel):
    candidate_id: int
    candidate_markdown: str | None = None


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


class SkillKnowPromptOut(BaseModel):
    id: int
    key: str
    category: SkillKnowPromptCategory
    name: str
    description: str | None
    content: str
    variables: list[str]
    is_active: bool
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


class SkillKnowLearningCandidateOut(BaseModel):
    id: int
    question: str
    assistant_answer: str | None
    feedback_reason: str | None
    correct_answer: str | None
    source_conversation_id: int | None
    source_message_id: int | None
    status: SkillKnowLearningStatus
    candidate_markdown: str | None
    reviewed_by: int | None
    reviewed_at: datetime | str | None = None
    extra_metadata: dict[str, Any]
    created_at: datetime | str | None = None
    updated_at: datetime | str | None = None


SkillKnowFolderOut.model_rebuild()
