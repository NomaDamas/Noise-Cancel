from __future__ import annotations

from fastapi import APIRouter

from .actions import router as actions_router
from .posts import router as posts_router

router = APIRouter(prefix="/api")
router.include_router(posts_router)
router.include_router(actions_router)

__all__ = ["router"]
