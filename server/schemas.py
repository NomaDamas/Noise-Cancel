from __future__ import annotations

from pydantic import BaseModel, Field


class PostResponse(BaseModel):
    id: str
    classification_id: str
    platform: str
    author_name: str
    author_url: str
    post_url: str
    post_text: str
    summary: str
    category: str
    confidence: float
    reasoning: str
    classified_at: str
    swipe_status: str
    note: str | None = None


class PostListResponse(BaseModel):
    posts: list[PostResponse]
    total: int
    has_more: bool


class ArchiveResponse(BaseModel):
    status: str
    classification_id: str


class ArchivePostResponse(ArchiveResponse):
    author_name: str
    summary: str
    post_url: str
    post_text: str
    category: str


class DeleteResponse(BaseModel):
    status: str
    classification_id: str


class NoteUpsertRequest(BaseModel):
    note_text: str = Field(min_length=1)


class NoteResponse(BaseModel):
    classification_id: str
    note: str | None


class NoteDeleteResponse(BaseModel):
    status: str
    classification_id: str


class PipelineRunRequest(BaseModel):
    limit: int = 50
    skip_scrape: bool = False


class PipelineRunResponse(BaseModel):
    run_id: str
    status: str
    message: str


class PipelineStatusResponse(BaseModel):
    run_id: str
    run_type: str
    started_at: str
    finished_at: str | None = None
    status: str
    posts_scraped: int
    posts_classified: int
    posts_delivered: int
    error_message: str | None = None


class DigestGenerateResponse(BaseModel):
    digest_text: str
