from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from noise_cancel.config import AppConfig
from noise_cancel.logger.repository import insert_classification, insert_post, insert_run_log
from noise_cancel.models import Classification, Post, RunLog
from server.main import create_app


def _test_config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        general={"data_dir": str(tmp_path / "data"), "max_posts_per_run": 50, "language": "english"},
        scraper={"headless": True, "scroll_count": 1},
        classifier={
            "model": "claude-sonnet-4-6",
            "batch_size": 10,
            "temperature": 0.0,
            "categories": [],
            "whitelist": {"keywords": [], "authors": []},
            "blacklist": {"keywords": [], "authors": []},
        },
        delivery={"method": "slack", "slack": {"include_categories": ["Read"]}},
    )


def _build_client(tmp_path: Path, monkeypatch) -> tuple[TestClient, sqlite3.Connection]:
    monkeypatch.setattr("server.main.load_config", lambda: _test_config(tmp_path))
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    monkeypatch.setattr("server.main.get_connection", lambda _: conn)
    return TestClient(create_app()), conn


def _seed_feedback(conn: sqlite3.Connection) -> None:
    insert_run_log(conn, RunLog(id="run-1", run_type="full", started_at="2026-02-25T00:00:00+00:00"))
    insert_post(
        conn,
        Post(
            id="post-1",
            platform="linkedin",
            author_name="Alice",
            post_text="Post one",
            run_id="run-1",
            scraped_at="2026-02-25T00:00:00+00:00",
        ),
    )
    insert_post(
        conn,
        Post(
            id="post-2",
            platform="x",
            author_name="Bob",
            post_text="Post two",
            run_id="run-1",
            scraped_at="2026-02-25T00:00:00+00:00",
        ),
    )
    insert_classification(
        conn,
        Classification(
            id="cls-1",
            post_id="post-1",
            category="Read",
            confidence=0.9,
            reasoning="Reasoning one",
            summary="Summary one",
            model_used="test-model",
            classified_at="2026-02-25T10:00:00+00:00",
        ),
    )
    insert_classification(
        conn,
        Classification(
            id="cls-2",
            post_id="post-2",
            category="Skip",
            confidence=0.2,
            reasoning="Reasoning two",
            summary="Summary two",
            model_used="test-model",
            classified_at="2026-02-25T11:00:00+00:00",
        ),
    )
    conn.execute(
        """INSERT INTO feedback
           (id, classification_id, action, platform, category, confidence, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?), (?, ?, ?, ?, ?, ?, ?)""",
        (
            "fb-1",
            "cls-1",
            "delete",
            "linkedin",
            "Read",
            0.9,
            "2026-02-25T12:00:00+00:00",
            "fb-2",
            "cls-2",
            "archive",
            "x",
            "Skip",
            0.2,
            "2026-02-25T12:01:00+00:00",
        ),
    )
    conn.commit()


def test_feedback_stats_returns_aggregated_payload(tmp_path: Path, monkeypatch) -> None:
    client, conn = _build_client(tmp_path, monkeypatch)
    with client:
        _seed_feedback(conn)

        response = client.get("/api/feedback/stats")
        assert response.status_code == 200

        payload = response.json()
        assert payload["total_feedback"] == 2
        assert payload["by_platform"] == [
            {
                "platform": "linkedin",
                "archive_count": 0,
                "delete_count": 1,
                "total": 1,
                "archive_ratio": 0.0,
                "delete_ratio": 1.0,
            },
            {
                "platform": "x",
                "archive_count": 1,
                "delete_count": 0,
                "total": 1,
                "archive_ratio": 1.0,
                "delete_ratio": 0.0,
            },
        ]
        assert payload["by_category"] == [
            {
                "category": "Read",
                "archive_count": 0,
                "delete_count": 1,
                "total": 1,
                "archive_ratio": 0.0,
                "delete_ratio": 1.0,
            },
            {
                "category": "Skip",
                "archive_count": 1,
                "delete_count": 0,
                "total": 1,
                "archive_ratio": 1.0,
                "delete_ratio": 0.0,
            },
        ]
        assert payload["override_confidence"] == {
            "total_overrides": 2,
            "average_confidence": 0.55,
            "distribution": [
                {"bucket": "0.0-0.2", "count": 0},
                {"bucket": "0.2-0.4", "count": 1},
                {"bucket": "0.4-0.6", "count": 0},
                {"bucket": "0.6-0.8", "count": 0},
                {"bucket": "0.8-1.0", "count": 1},
            ],
        }
