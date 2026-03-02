from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from noise_cancel.config import AppConfig
from noise_cancel.logger.repository import insert_classification, insert_post, insert_run_log, update_swipe_status
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


def _post(post_id: str, run_id: str = "run-1", platform: str = "linkedin") -> Post:
    return Post(
        id=post_id,
        platform=platform,
        author_name=f"Author {post_id}",
        author_url=f"https://linkedin.com/in/{post_id}",
        post_url=f"https://linkedin.com/posts/{post_id}",
        post_text=f"Post text {post_id}",
        run_id=run_id,
        scraped_at="2026-02-25T00:00:00+00:00",
    )


def _classification(
    classification_id: str,
    post_id: str,
    *,
    category: str,
    classified_at: str,
) -> Classification:
    return Classification(
        id=classification_id,
        post_id=post_id,
        category=category,
        confidence=0.95,
        reasoning=f"Reasoning for {classification_id}",
        summary=f"Summary for {classification_id}",
        model_used="test-model",
        classified_at=classified_at,
    )


def _seed_feed_data(conn: sqlite3.Connection) -> None:
    insert_run_log(
        conn,
        RunLog(
            id="run-1",
            run_type="full",
            started_at="2026-02-25T00:00:00+00:00",
        ),
    )

    insert_post(conn, _post("post-1", platform="linkedin"))
    insert_post(conn, _post("post-2", platform="x"))
    insert_post(conn, _post("post-3", platform="reddit"))
    insert_post(conn, _post("post-4", platform="threads"))
    insert_post(conn, _post("post-5", platform="linkedin"))

    insert_classification(
        conn,
        _classification(
            "cls-1",
            "post-1",
            category="Read",
            classified_at="2026-02-25T10:00:00+00:00",
        ),
    )
    insert_classification(
        conn,
        _classification(
            "cls-2",
            "post-2",
            category="Read",
            classified_at="2026-02-25T11:00:00+00:00",
        ),
    )
    insert_classification(
        conn,
        _classification(
            "cls-3",
            "post-3",
            category="Skip",
            classified_at="2026-02-25T12:00:00+00:00",
        ),
    )
    insert_classification(
        conn,
        _classification(
            "cls-4",
            "post-4",
            category="Read",
            classified_at="2026-02-25T09:00:00+00:00",
        ),
    )
    insert_classification(
        conn,
        _classification(
            "cls-5",
            "post-5",
            category="Read",
            classified_at="2026-02-25T08:00:00+00:00",
        ),
    )
    update_swipe_status(conn, "cls-4", "archived")


def _build_client(tmp_path: Path, monkeypatch) -> tuple[TestClient, sqlite3.Connection]:
    monkeypatch.setattr("server.main.load_config", lambda: _test_config(tmp_path))
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    monkeypatch.setattr("server.main.get_connection", lambda _: conn)
    return TestClient(create_app()), conn


def test_get_posts_default_response_shape(tmp_path: Path, monkeypatch) -> None:
    client, conn = _build_client(tmp_path, monkeypatch)
    with client:
        _seed_feed_data(conn)

        response = client.get("/api/posts")
        assert response.status_code == 200

        payload = response.json()
        assert set(payload) == {"posts", "total", "has_more"}
        assert payload["total"] == 3
        assert payload["has_more"] is False
        assert [post["classification_id"] for post in payload["posts"]] == ["cls-2", "cls-1", "cls-5"]

        first = payload["posts"][0]
        assert set(first) == {
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
        }
        assert first["category"] == "Read"
        assert first["platform"] == "x"
        assert first["swipe_status"] == "pending"


def test_get_posts_filters_by_category_and_swipe_status(tmp_path: Path, monkeypatch) -> None:
    client, conn = _build_client(tmp_path, monkeypatch)
    with client:
        _seed_feed_data(conn)

        skip = client.get("/api/posts", params={"category": "Skip", "swipe_status": "pending"})
        assert skip.status_code == 200
        skip_payload = skip.json()
        assert skip_payload["total"] == 1
        assert [post["classification_id"] for post in skip_payload["posts"]] == ["cls-3"]

        archived = client.get("/api/posts", params={"category": "Read", "swipe_status": "archived"})
        assert archived.status_code == 200
        archived_payload = archived.json()
        assert archived_payload["total"] == 1
        assert [post["classification_id"] for post in archived_payload["posts"]] == ["cls-4"]
        assert archived_payload["posts"][0]["swipe_status"] == "archived"


def test_get_posts_filters_by_platform(tmp_path: Path, monkeypatch) -> None:
    client, conn = _build_client(tmp_path, monkeypatch)
    with client:
        _seed_feed_data(conn)

        response = client.get(
            "/api/posts",
            params={"category": "Read", "swipe_status": "pending", "platform": "linkedin"},
        )
        assert response.status_code == 200

        payload = response.json()
        assert payload["total"] == 2
        assert [post["classification_id"] for post in payload["posts"]] == ["cls-1", "cls-5"]
        assert {post["platform"] for post in payload["posts"]} == {"linkedin"}


def test_get_posts_pagination_computes_has_more(tmp_path: Path, monkeypatch) -> None:
    client, conn = _build_client(tmp_path, monkeypatch)
    with client:
        _seed_feed_data(conn)

        first_page = client.get(
            "/api/posts",
            params={"category": "Read", "swipe_status": "pending", "limit": 2, "offset": 0},
        )
        assert first_page.status_code == 200
        first_payload = first_page.json()
        assert first_payload["total"] == 3
        assert first_payload["has_more"] is True
        assert [post["classification_id"] for post in first_payload["posts"]] == ["cls-2", "cls-1"]

        second_page = client.get(
            "/api/posts",
            params={"category": "Read", "swipe_status": "pending", "limit": 2, "offset": 2},
        )
        assert second_page.status_code == 200
        second_payload = second_page.json()
        assert second_payload["total"] == 3
        assert second_payload["has_more"] is False
        assert [post["classification_id"] for post in second_payload["posts"]] == ["cls-5"]


def test_get_post_detail_returns_post_for_valid_classification_id(tmp_path: Path, monkeypatch) -> None:
    client, conn = _build_client(tmp_path, monkeypatch)
    with client:
        _seed_feed_data(conn)

        response = client.get("/api/posts/cls-2")
        assert response.status_code == 200

        payload = response.json()
        assert payload["classification_id"] == "cls-2"
        assert payload["id"] == "post-2"
        assert payload["category"] == "Read"
        assert payload["summary"] == "Summary for cls-2"
        assert payload["platform"] == "x"
        assert payload["swipe_status"] == "pending"


def test_get_post_detail_returns_404_for_missing_classification_id(tmp_path: Path, monkeypatch) -> None:
    client, conn = _build_client(tmp_path, monkeypatch)
    with client:
        _seed_feed_data(conn)

        response = client.get("/api/posts/missing")
        assert response.status_code == 404
        assert response.json() == {"detail": "Not found"}
