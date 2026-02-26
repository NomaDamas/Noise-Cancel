from __future__ import annotations

import sqlite3
from typing import cast

from fastapi import Request

from noise_cancel.config import AppConfig


def get_db(request: Request) -> sqlite3.Connection:
    return cast(sqlite3.Connection, request.app.state.db)


def get_config(request: Request) -> AppConfig:
    return cast(AppConfig, request.app.state.config)
