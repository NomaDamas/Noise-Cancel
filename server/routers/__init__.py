from __future__ import annotations

from fastapi import APIRouter

from .actions import router as actions_router
from .pipeline import router as pipeline_router
from .posts import router as posts_router

router = APIRouter(prefix="/api")
router.include_router(posts_router)
router.include_router(actions_router)
router.include_router(pipeline_router)

__all__ = ["router"]
