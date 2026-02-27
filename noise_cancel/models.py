from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


class Post(BaseModel):
    id: str
    platform: str = "linkedin"
    author_name: str
    author_url: str | None = None
    post_url: str | None = None
    post_text: str
    content_hash: str | None = None
    media_type: str | None = None
    post_timestamp: str | None = None
    scraped_at: str = Field(default_factory=_now_iso)
    run_id: str | None = None

    def to_dict(self) -> dict:
        return self.model_dump()


class Classification(BaseModel):
    id: str
    post_id: str
    category: str
    confidence: float
    reasoning: str
    summary: str = ""
    applied_rules: list[str] = Field(default_factory=list)
    model_used: str
    classified_at: str = Field(default_factory=_now_iso)
    delivered: bool = False
    delivered_at: str | None = None

    def to_dict(self) -> dict:
        d = self.model_dump()
        d["delivered"] = int(d["delivered"])
        return d


class RunLog(BaseModel):
    id: str
    run_type: str
    started_at: str = Field(default_factory=_now_iso)
    finished_at: str | None = None
    status: str = "running"
    posts_scraped: int = 0
    posts_classified: int = 0
    posts_delivered: int = 0
    error_message: str | None = None

    def to_dict(self) -> dict:
        return self.model_dump()
