from __future__ import annotations

from fastapi import APIRouter

from .actions import router as actions_router
from .digest import router as digest_router
from .feedback import router as feedback_router
from .pipeline import router as pipeline_router
from .posts import router as posts_router

router = APIRouter(prefix="/api")
router.include_router(posts_router)
router.include_router(actions_router)
router.include_router(pipeline_router)
router.include_router(digest_router)
router.include_router(feedback_router)

__all__ = ["router"]
