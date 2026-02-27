from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, cast

from fastapi import FastAPI
from fastapi.middleware import Middleware
from fastapi.middleware.cors import CORSMiddleware

from noise_cancel.config import AppConfig, load_config
from noise_cancel.database import apply_migrations, get_connection
from server.routers import router as api_router

ASGIReceive = Callable[[], Awaitable[Any]]
ASGISend = Callable[[Any], Awaitable[None]]
ASGIApp = Callable[[Any, ASGIReceive, ASGISend], Awaitable[None]]
MiddlewareFactory = Callable[..., ASGIApp]
logger = logging.getLogger(__name__)


def _resolve_db_path(config: AppConfig) -> Path:
    data_dir = Path(config.general["data_dir"])
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "noise_cancel.db"


def _resolve_cors_origins(config: AppConfig) -> list[str]:
    raw_origins = config.server.get("cors_origins")
    if not isinstance(raw_origins, list):
        return ["*"]

    origins = [origin for origin in raw_origins if isinstance(origin, str) and origin.strip()]
    return origins or ["*"]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    config = cast(AppConfig, getattr(app.state, "config", load_config()))
    cors_origins = cast(list[str], getattr(app.state, "cors_origins", _resolve_cors_origins(config)))
    if "*" in cors_origins:
        logger.warning("Wildcard CORS origin is active; all origins can access the API.")

    conn = get_connection(str(_resolve_db_path(config)))
    apply_migrations(conn)

    app.state.db = conn

    try:
        yield
    finally:
        conn.close()


def create_app() -> FastAPI:
    config = load_config()
    cors_origins = _resolve_cors_origins(config)

    cors_middleware = cast(MiddlewareFactory, CORSMiddleware)
    middleware = [
        Middleware(
            cors_middleware,
            allow_origins=cors_origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    ]
    app = FastAPI(title="NoiseCancel API", lifespan=lifespan, middleware=middleware)
    app.state.config = config
    app.state.cors_origins = cors_origins
    app.include_router(api_router)
    return app


app = create_app()
