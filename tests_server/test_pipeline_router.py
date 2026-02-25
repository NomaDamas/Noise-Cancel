from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from noise_cancel.classifier.schemas import PostClassification
from noise_cancel.config import AppConfig
from noise_cancel.logger.repository import insert_run_log
from noise_cancel.models import Post, RunLog
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


def test_run_pipeline_creates_run_log_and_returns_accepted(tmp_path: Path, monkeypatch) -> None:
    class FakeScraper:
        def __init__(self, _config: AppConfig) -> None:
            pass

        async def scrape_feed(self, scroll_count: int = 10) -> list[Post]:
            assert scroll_count == 1
            return [
                Post(
                    id="post-1",
                    author_name="Author One",
                    author_url="https://linkedin.com/in/one",
                    post_url="https://linkedin.com/posts/one",
                    post_text="First post",
                ),
                Post(
                    id="post-2",
                    author_name="Author Two",
                    author_url="https://linkedin.com/in/two",
                    post_url="https://linkedin.com/posts/two",
                    post_text="Second post",
                ),
            ]

    class FakeClassifier:
        def __init__(self, _config: AppConfig) -> None:
            pass

        def classify_posts(self, posts: list[Post]) -> list[PostClassification]:
            assert [post.id for post in posts] == ["post-1"]
            return [
                PostClassification(
                    post_index=0,
                    category="Read",
                    confidence=0.96,
                    reasoning="Useful",
                    summary="Keep this one",
                    applied_rules=[],
                )
            ]

    monkeypatch.setattr("server.services.pipeline.LinkedInScraper", FakeScraper)
    monkeypatch.setattr("server.services.pipeline.ClassificationEngine", FakeClassifier)

    client, conn = _build_client(tmp_path, monkeypatch)
    with client:
        response = client.post(
            "/api/pipeline/run",
            json={"limit": 1, "skip_scrape": False},
        )

        assert response.status_code == 202
        payload = response.json()
        assert set(payload) == {"run_id", "status", "message"}
        assert payload["status"] == "accepted"

        run_log = conn.execute(
            "SELECT run_type, status, posts_scraped, posts_classified FROM run_logs WHERE id = ?",
            (payload["run_id"],),
        ).fetchone()
        assert run_log is not None
        assert run_log["run_type"] == "pipeline"
        assert run_log["status"] == "completed"
        assert run_log["posts_scraped"] == 1
        assert run_log["posts_classified"] == 1


def test_run_pipeline_allows_empty_body(tmp_path: Path, monkeypatch) -> None:
    class FakeScraper:
        def __init__(self, _config: AppConfig) -> None:
            pass

        async def scrape_feed(self, scroll_count: int = 10) -> list[Post]:
            assert scroll_count == 1
            return []

    class FakeClassifier:
        def __init__(self, _config: AppConfig) -> None:
            pass

        def classify_posts(self, posts: list[Post]) -> list[PostClassification]:
            assert posts == []
            return []

    monkeypatch.setattr("server.services.pipeline.LinkedInScraper", FakeScraper)
    monkeypatch.setattr("server.services.pipeline.ClassificationEngine", FakeClassifier)

    client, conn = _build_client(tmp_path, monkeypatch)
    with client:
        response = client.post("/api/pipeline/run")

        assert response.status_code == 202
        payload = response.json()
        run_log = conn.execute("SELECT id, run_type FROM run_logs WHERE id = ?", (payload["run_id"],)).fetchone()
        assert run_log is not None
        assert run_log["run_type"] == "pipeline"


def test_get_pipeline_status_returns_latest_run(tmp_path: Path, monkeypatch) -> None:
    client, conn = _build_client(tmp_path, monkeypatch)
    with client:
        insert_run_log(
            conn,
            RunLog(
                id="run-old",
                run_type="pipeline",
                started_at="2026-02-24T01:00:00+00:00",
                status="completed",
                posts_scraped=2,
                posts_classified=2,
                posts_delivered=0,
            ),
        )
        insert_run_log(
            conn,
            RunLog(
                id="run-new",
                run_type="pipeline",
                started_at="2026-02-25T01:00:00+00:00",
                status="running",
                posts_scraped=1,
                posts_classified=0,
                posts_delivered=0,
            ),
        )

        response = client.get("/api/pipeline/status")
        assert response.status_code == 200
        payload = response.json()
        assert payload["run_id"] == "run-new"
        assert payload["run_type"] == "pipeline"
        assert payload["status"] == "running"
        assert payload["posts_scraped"] == 1
        assert payload["posts_classified"] == 0
