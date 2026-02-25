from __future__ import annotations

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from noise_cancel.logger.repository import count_posts_for_feed, get_posts_for_feed
from server.dependencies import get_db
from server.schemas import PostListResponse, PostResponse

router = APIRouter(tags=["posts"])


@router.get("/posts", response_model=PostListResponse)
def get_posts(
    db: Annotated[sqlite3.Connection, Depends(get_db)],
    category: str = Query(default="Read"),
    swipe_status: str = Query(default="pending"),
    limit: int = Query(default=20, ge=1),
    offset: int = Query(default=0, ge=0),
) -> PostListResponse:
    rows = get_posts_for_feed(
        conn=db,
        category=category,
        swipe_status=swipe_status,
        limit=limit,
        offset=offset,
    )
    total = count_posts_for_feed(conn=db, category=category, swipe_status=swipe_status)
    posts = [PostResponse.model_validate(row) for row in rows]
    has_more = total > (offset + limit)
    return PostListResponse(posts=posts, total=total, has_more=has_more)
