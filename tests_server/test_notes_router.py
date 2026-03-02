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
            post_text="Post text for note test",
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


def test_post_and_get_note_round_trip(tmp_path: Path, monkeypatch) -> None:
    client, conn = _build_client(tmp_path, monkeypatch)
    with client:
        _seed_data(conn)

        create = client.post("/api/posts/cls-1/note", json={"note_text": "Track this for next sprint"})
        assert create.status_code == 200
        assert create.json() == {
            "classification_id": "cls-1",
            "note": "Track this for next sprint",
        }

        row = conn.execute(
            "SELECT classification_id, note_text, created_at, updated_at FROM notes WHERE classification_id = ?",
            ("cls-1",),
        ).fetchone()
        assert row is not None
        assert row["classification_id"] == "cls-1"
        assert row["note_text"] == "Track this for next sprint"
        assert row["created_at"] is not None
        assert row["updated_at"] is not None

        read = client.get("/api/posts/cls-1/note")
        assert read.status_code == 200
        assert read.json() == {
            "classification_id": "cls-1",
            "note": "Track this for next sprint",
        }


def test_post_note_updates_existing_note(tmp_path: Path, monkeypatch) -> None:
    client, conn = _build_client(tmp_path, monkeypatch)
    with client:
        _seed_data(conn)

        first = client.post("/api/posts/cls-1/note", json={"note_text": "first"})
        assert first.status_code == 200

        second = client.post("/api/posts/cls-1/note", json={"note_text": "second"})
        assert second.status_code == 200
        assert second.json() == {"classification_id": "cls-1", "note": "second"}

        count = conn.execute(
            "SELECT COUNT(*) AS total FROM notes WHERE classification_id = ?",
            ("cls-1",),
        ).fetchone()
        assert count is not None
        assert count["total"] == 1


def test_delete_note_removes_record_and_returns_success(tmp_path: Path, monkeypatch) -> None:
    client, conn = _build_client(tmp_path, monkeypatch)
    with client:
        _seed_data(conn)
        created = client.post("/api/posts/cls-1/note", json={"note_text": "delete me"})
        assert created.status_code == 200

        deleted = client.delete("/api/posts/cls-1/note")
        assert deleted.status_code == 200
        assert deleted.json() == {"status": "deleted", "classification_id": "cls-1"}

        row = conn.execute(
            "SELECT id FROM notes WHERE classification_id = ?",
            ("cls-1",),
        ).fetchone()
        assert row is None

        read = client.get("/api/posts/cls-1/note")
        assert read.status_code == 200
        assert read.json() == {"classification_id": "cls-1", "note": None}


def test_note_endpoints_return_404_for_missing_classification_id(tmp_path: Path, monkeypatch) -> None:
    client, conn = _build_client(tmp_path, monkeypatch)
    with client:
        _seed_data(conn)

        create = client.post("/api/posts/missing/note", json={"note_text": "x"})
        read = client.get("/api/posts/missing/note")
        delete = client.delete("/api/posts/missing/note")

        assert create.status_code == 404
        assert read.status_code == 404
        assert delete.status_code == 404

        assert create.json() == {"detail": "Not found"}
        assert read.json() == {"detail": "Not found"}
        assert delete.json() == {"detail": "Not found"}


def test_post_note_rejects_blank_note_text(tmp_path: Path, monkeypatch) -> None:
    client, conn = _build_client(tmp_path, monkeypatch)
    with client:
        _seed_data(conn)

        response = client.post("/api/posts/cls-1/note", json={"note_text": "   "})
        assert response.status_code == 422
