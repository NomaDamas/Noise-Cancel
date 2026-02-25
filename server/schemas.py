from __future__ import annotations

from pydantic import BaseModel


class PostResponse(BaseModel):
    id: str
    classification_id: str
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


class PostListResponse(BaseModel):
    posts: list[PostResponse]
    total: int
    has_more: bool


class ArchiveResponse(BaseModel):
    status: str
    classification_id: str


class DeleteResponse(BaseModel):
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
