from pydantic import BaseModel, Field


class WikiAskIn(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    conversation_id: int | None = None


class WikiLearningReviewIn(BaseModel):
    candidate_id: int
    content: str | None = None


class WikiRejectIn(BaseModel):
    candidate_id: int


class WikiFeedbackIn(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    answer: str | None = None
    evidence_page_ids: list[int] = Field(default_factory=list)


class WikiPageSaveIn(BaseModel):
    page_id: int | None = None
    path: str | None = Field(default=None, max_length=255)
    title: str = Field(..., min_length=1, max_length=200)
    page_type: str = Field(default="concept", max_length=30)
    summary: str | None = None
    content: str = Field(..., min_length=1)


class WikiDictionaryIn(BaseModel):
    domain_terms: list[str] = Field(default_factory=list)
    stop_words: list[str] = Field(default_factory=list)


class WikiUploadInitIn(BaseModel):
    filename: str = Field(..., min_length=1, max_length=255)
    file_size: int = Field(default=0, ge=0)
    total_chunks: int = Field(..., ge=1)


class WikiUploadCompleteIn(BaseModel):
    upload_id: str = Field(..., min_length=1, max_length=80)
    filename: str = Field(..., min_length=1, max_length=255)
    total_chunks: int = Field(..., ge=1)
