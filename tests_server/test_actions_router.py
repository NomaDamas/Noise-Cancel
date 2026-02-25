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


def _seed_data(conn: sqlite3.Connection) -> None:
    insert_run_log(
        conn,
        RunLog(
            id="run-1",
            run_type="full",
            started_at="2026-02-25T00:00:00+00:00",
        ),
    )

    insert_post(
        conn,
        Post(
            id="post-1",
            author_name="Jane Doe",
            author_url="https://linkedin.com/in/jane",
            post_url="https://linkedin.com/posts/post-1",
            post_text="Post text for archive test",
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
            confidence=0.95,
            reasoning="Reasoning for cls-1",
            summary="Summary for cls-1",
            model_used="test-model",
            classified_at="2026-02-25T10:00:00+00:00",
        ),
    )


def _build_client(tmp_path: Path, monkeypatch) -> tuple[TestClient, sqlite3.Connection]:
    monkeypatch.setattr("server.main.load_config", lambda: _test_config(tmp_path))
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    monkeypatch.setattr("server.main.get_connection", lambda _: conn)
    return TestClient(create_app()), conn


def test_archive_updates_status_and_returns_archive_payload(tmp_path: Path, monkeypatch) -> None:
    client, conn = _build_client(tmp_path, monkeypatch)
    with client:
        _seed_data(conn)

        response = client.post("/api/posts/cls-1/archive")
        assert response.status_code == 200

        payload = response.json()
        assert set(payload) == {
            "status",
            "classification_id",
            "author_name",
            "summary",
            "post_url",
            "post_text",
            "category",
        }
        assert payload["status"] == "archived"
        assert payload["classification_id"] == "cls-1"
        assert payload["author_name"] == "Jane Doe"
        assert payload["summary"] == "Summary for cls-1"
        assert payload["post_url"] == "https://linkedin.com/posts/post-1"
        assert payload["post_text"] == "Post text for archive test"
        assert payload["category"] == "Read"

        row = conn.execute(
            "SELECT swipe_status FROM classifications WHERE id = ?",
            ("cls-1",),
        ).fetchone()
        assert row is not None
        assert row["swipe_status"] == "archived"


def test_archive_returns_404_for_missing_classification_id(tmp_path: Path, monkeypatch) -> None:
    client, conn = _build_client(tmp_path, monkeypatch)
    with client:
        _seed_data(conn)

        response = client.post("/api/posts/missing/archive")
        assert response.status_code == 404
        assert response.json() == {"detail": "Not found"}
