from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from noise_cancel.config import AppConfig
from noise_cancel.digest.service import DigestRunResult
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


def test_generate_digest_endpoint_returns_digest_text(tmp_path: Path, monkeypatch) -> None:
    digest_result = DigestRunResult(
        digest_text="Daily Feed Digest\n\nDigest body",
        delivered_plugins=1,
        delivery_enabled=True,
    )

    monkeypatch.setattr(
        "server.routers.digest.generate_and_deliver_digest",
        lambda conn, config: digest_result,
    )

    client, _ = _build_client(tmp_path, monkeypatch)
    with client:
        response = client.post("/api/digest/generate")

    assert response.status_code == 200
    payload = response.json()
    assert payload["digest_text"] == "Daily Feed Digest\n\nDigest body"
