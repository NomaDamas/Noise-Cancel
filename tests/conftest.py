from __future__ import annotations

import sqlite3
from collections.abc import Generator
from pathlib import Path

import pytest

from noise_cancel.config import AppConfig
from noise_cancel.database import apply_migrations, get_connection


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    return tmp_path / "noise-cancel-data"


@pytest.fixture
def app_config(tmp_data_dir: Path) -> AppConfig:
    return AppConfig(
        general={"data_dir": str(tmp_data_dir), "max_posts_per_run": 50},
        scraper={"headless": True, "scroll_count": 5},
        classifier={
            "model": "claude-sonnet-4-6",
            "batch_size": 10,
            "temperature": 0.0,
            "categories": [],
            "whitelist": {"keywords": [], "authors": []},
            "blacklist": {"keywords": [], "authors": []},
        },
        delivery={
            "method": "slack",
            "slack": {
                "include_categories": ["Read"],
                "include_reasoning": True,
                "max_text_preview": 300,
            },
        },
    )


@pytest.fixture
def db_connection(tmp_data_dir: Path) -> Generator[sqlite3.Connection]:
    tmp_data_dir.mkdir(parents=True, exist_ok=True)
    db_path = tmp_data_dir / "noise_cancel.db"
    conn = get_connection(str(db_path))
    apply_migrations(conn)
    yield conn
    conn.close()
