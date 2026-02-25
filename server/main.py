from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, cast

from fastapi import FastAPI
from fastapi.middleware import Middleware
from fastapi.middleware.cors import CORSMiddleware

from noise_cancel.config import AppConfig, load_config
from noise_cancel.database import apply_migrations, get_connection

ASGIReceive = Callable[[], Awaitable[Any]]
ASGISend = Callable[[Any], Awaitable[None]]
ASGIApp = Callable[[Any, ASGIReceive, ASGISend], Awaitable[None]]
MiddlewareFactory = Callable[..., ASGIApp]


def _resolve_db_path(config: AppConfig) -> Path:
    data_dir = Path(config.general["data_dir"])
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "noise_cancel.db"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    config = load_config()
    conn = get_connection(str(_resolve_db_path(config)))
    apply_migrations(conn)

    app.state.config = config
    app.state.db = conn

    try:
        yield
    finally:
        conn.close()


def create_app() -> FastAPI:
    cors_middleware = cast(MiddlewareFactory, CORSMiddleware)
    middleware = [
        Middleware(
            cors_middleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )
    ]
    app = FastAPI(title="NoiseCancel API", lifespan=lifespan, middleware=middleware)
    return app


app = create_app()
