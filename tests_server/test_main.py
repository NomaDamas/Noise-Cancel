from __future__ import annotations

import sqlite3
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from noise_cancel.config import AppConfig


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
        server={"cors_origins": ["*"]},
    )


def test_create_app_exports_fastapi_app():
    from server.main import app, create_app

    created_app = create_app()
    assert app.title == created_app.title
    assert hasattr(created_app, "router")


def test_lifespan_loads_config_opens_db_and_runs_migrations(tmp_path: Path, monkeypatch):
    from server.main import create_app

    config = _test_config(tmp_path)
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    load_calls: list[SimpleNamespace] = []

    def fake_load_config() -> AppConfig:
        load_calls.append(SimpleNamespace(called=True))
        return config

    captured_db_path: list[str] = []

    def fake_get_connection(db_path: str) -> sqlite3.Connection:
        captured_db_path.append(db_path)
        return conn

    migration_calls: list[sqlite3.Connection] = []

    def fake_apply_migrations(db_conn: sqlite3.Connection) -> None:
        migration_calls.append(db_conn)

    monkeypatch.setattr("server.main.load_config", fake_load_config)
    monkeypatch.setattr("server.main.get_connection", fake_get_connection)
    monkeypatch.setattr("server.main.apply_migrations", fake_apply_migrations)

    app = create_app()
    with TestClient(app):
        assert app.state.config == config
        assert app.state.db == conn

    assert load_calls
    assert captured_db_path
    assert Path(captured_db_path[0]).name == "noise_cancel.db"
    assert migration_calls == [conn]


def test_create_app_configures_wide_open_cors(tmp_path: Path, monkeypatch):
    from server.main import create_app

    monkeypatch.setattr("server.main.load_config", lambda: _test_config(tmp_path))
    app = create_app()
    cors = next((m for m in app.user_middleware if "allow_origins" in m.kwargs), None)
    assert cors is not None
    assert cors.kwargs["allow_origins"] == ["*"]
    assert cors.kwargs["allow_methods"] == ["*"]
    assert cors.kwargs["allow_headers"] == ["*"]


def test_create_app_uses_configured_cors_origins(tmp_path: Path, monkeypatch):
    from server.main import create_app

    config = _test_config(tmp_path)
    config.server = {"cors_origins": ["https://app.example.com", "https://localhost:3000"]}
    monkeypatch.setattr("server.main.load_config", lambda: config)

    app = create_app()
    cors = next((m for m in app.user_middleware if "allow_origins" in m.kwargs), None)

    assert cors is not None
    assert cors.kwargs["allow_origins"] == ["https://app.example.com", "https://localhost:3000"]


def test_lifespan_warns_when_wildcard_cors_is_active(tmp_path: Path, monkeypatch, caplog):
    from server.main import create_app

    config = _test_config(tmp_path)
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    monkeypatch.setattr("server.main.load_config", lambda: config)
    monkeypatch.setattr("server.main.get_connection", lambda db_path: conn)
    monkeypatch.setattr("server.main.apply_migrations", lambda db_conn: None)
    caplog.set_level("WARNING", logger="server.main")

    app = create_app()
    with TestClient(app):
        pass

    assert "Wildcard CORS origin" in caplog.text


def test_docs_endpoint_is_available(tmp_path: Path, monkeypatch):
    from server.main import create_app

    config = _test_config(tmp_path)
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    monkeypatch.setattr("server.main.load_config", lambda: config)
    monkeypatch.setattr("server.main.get_connection", lambda db_path: conn)
    monkeypatch.setattr("server.main.apply_migrations", lambda db_conn: None)

    app = create_app()
    with TestClient(app) as client:
        response = client.get("/docs")
    assert response.status_code == 200
    assert "Swagger UI" in response.text
