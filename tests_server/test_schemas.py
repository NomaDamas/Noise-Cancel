from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from server.schemas import (
    ArchiveResponse,
    DeleteResponse,
    NoteDeleteResponse,
    NoteResponse,
    NoteUpsertRequest,
    PipelineRunRequest,
    PipelineRunResponse,
    PipelineStatusResponse,
    PostListResponse,
    PostResponse,
)


def _sample_post_payload() -> dict[str, object]:
    return {
        "id": "post-1",
        "classification_id": "cls-1",
        "platform": "linkedin",
        "author_name": "Jane Doe",
        "author_url": "https://linkedin.com/in/jane",
        "post_url": "https://linkedin.com/posts/1",
        "post_text": "Interesting post body",
        "summary": "Short summary",
        "category": "Read",
        "confidence": 0.92,
        "reasoning": "Matches whitelist keywords.",
        "classified_at": "2026-02-25T00:00:00+00:00",
        "swipe_status": "pending",
        "note": None,
    }


def test_all_schema_classes_are_pydantic_models():
    schema_classes = [
        PostResponse,
        PostListResponse,
        ArchiveResponse,
        DeleteResponse,
        NoteUpsertRequest,
        NoteResponse,
        NoteDeleteResponse,
        PipelineRunRequest,
        PipelineRunResponse,
        PipelineStatusResponse,
    ]
    assert all(issubclass(schema, BaseModel) for schema in schema_classes)


def test_post_response_schema_contract():
    expected_fields = {
        "id",
        "classification_id",
        "platform",
        "author_name",
        "author_url",
        "post_url",
        "post_text",
        "summary",
        "category",
        "confidence",
        "reasoning",
        "classified_at",
        "swipe_status",
        "note",
    }
    assert set(PostResponse.model_fields) == expected_fields

    payload = _sample_post_payload()
    post = PostResponse.model_validate(payload)

    assert post.model_dump() == payload

    bad_payload = _sample_post_payload()
    bad_payload["confidence"] = "not-a-float"
    with pytest.raises(ValidationError):
        PostResponse.model_validate(bad_payload)


def test_post_list_response_schema_contract():
    expected_fields = {"posts", "total", "has_more"}
    assert set(PostListResponse.model_fields) == expected_fields

    post = PostResponse.model_validate(_sample_post_payload())
    response = PostListResponse(posts=[post], total=1, has_more=False)

    assert response.total == 1
    assert response.has_more is False
    assert response.posts[0].classification_id == "cls-1"


def test_archive_and_delete_response_schema_contract():
    assert set(ArchiveResponse.model_fields) == {"status", "classification_id"}
    assert set(DeleteResponse.model_fields) == {"status", "classification_id"}

    archive = ArchiveResponse(status="archived", classification_id="cls-1")
    delete = DeleteResponse(status="deleted", classification_id="cls-2")

    assert archive.model_dump() == {"status": "archived", "classification_id": "cls-1"}
    assert delete.model_dump() == {"status": "deleted", "classification_id": "cls-2"}


def test_note_schema_contract():
    assert set(NoteUpsertRequest.model_fields) == {"note_text"}
    assert set(NoteResponse.model_fields) == {"classification_id", "note"}
    assert set(NoteDeleteResponse.model_fields) == {"status", "classification_id"}

    upsert = NoteUpsertRequest(note_text="Track this")
    response = NoteResponse(classification_id="cls-1", note="Track this")
    delete = NoteDeleteResponse(status="deleted", classification_id="cls-1")

    assert upsert.model_dump() == {"note_text": "Track this"}
    assert response.model_dump() == {"classification_id": "cls-1", "note": "Track this"}
    assert delete.model_dump() == {"status": "deleted", "classification_id": "cls-1"}


def test_pipeline_run_request_defaults():
    assert set(PipelineRunRequest.model_fields) == {"limit", "skip_scrape"}

    req = PipelineRunRequest()
    assert req.limit == 50
    assert req.skip_scrape is False


def test_pipeline_run_response_schema_contract():
    assert set(PipelineRunResponse.model_fields) == {"run_id", "status", "message"}

    response = PipelineRunResponse(run_id="run-1", status="running", message="Pipeline started")
    assert response.model_dump() == {"run_id": "run-1", "status": "running", "message": "Pipeline started"}


def test_pipeline_status_response_schema_contract():
    expected_fields = {
        "run_id",
        "run_type",
        "started_at",
        "finished_at",
        "status",
        "posts_scraped",
        "posts_classified",
        "posts_delivered",
        "error_message",
    }
    assert set(PipelineStatusResponse.model_fields) == expected_fields

    response = PipelineStatusResponse(
        run_id="run-1",
        run_type="manual",
        started_at="2026-02-25T00:00:00+00:00",
        finished_at="2026-02-25T00:01:00+00:00",
        status="completed",
        posts_scraped=10,
        posts_classified=9,
        posts_delivered=4,
        error_message="",
    )
    assert response.model_dump()["run_id"] == "run-1"
