from __future__ import annotations

from fastapi import APIRouter

from .posts import router as posts_router

router = APIRouter(prefix="/api")
router.include_router(posts_router)

__all__ = ["router"]
