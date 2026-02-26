from __future__ import annotations

import sqlite3
from types import SimpleNamespace

from fastapi import Request

from noise_cancel.config import AppConfig
from server.dependencies import get_config, get_db


def test_get_db_returns_connection_from_app_state():
    conn = sqlite3.connect(":memory:")
    request = Request({
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "app": SimpleNamespace(state=SimpleNamespace(db=conn)),
    })
    assert get_db(request) == conn


def test_get_config_returns_config_from_app_state():
    config = AppConfig(general={"data_dir": "test-data"})
    request = Request({
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "app": SimpleNamespace(state=SimpleNamespace(config=config)),
    })
    assert get_config(request) == config
