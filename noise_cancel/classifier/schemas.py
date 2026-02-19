from __future__ import annotations

from pydantic import BaseModel, Field


class PostClassification(BaseModel):
    post_index: int
    category: str
    confidence: float
    reasoning: str
    summary: str = ""
    applied_rules: list[str] = Field(default_factory=list)


class BatchClassificationResult(BaseModel):
    classifications: list[PostClassification]
