from __future__ import annotations

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from noise_cancel.logger.repository import (
    count_posts_for_feed,
    get_post_for_feed_by_classification_id,
    get_posts_for_feed,
)
from server.dependencies import get_db
from server.schemas import PostListResponse, PostResponse

router = APIRouter(tags=["posts"])


@router.get("/posts", response_model=PostListResponse)
def get_posts(
    db: Annotated[sqlite3.Connection, Depends(get_db)],
    category: str = Query(default="Read"),
    swipe_status: str = Query(default="pending"),
    platform: str | None = Query(default=None),
    q: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1),
    offset: int = Query(default=0, ge=0),
) -> PostListResponse:
    normalized_platform = platform.strip().lower() if platform and platform.strip() else None
    normalized_query = q.strip() if q and q.strip() else None
    rows = get_posts_for_feed(
        conn=db,
        category=category,
        swipe_status=swipe_status,
        platform=normalized_platform,
        query=normalized_query,
        limit=limit,
        offset=offset,
    )
    total = count_posts_for_feed(
        conn=db,
        category=category,
        swipe_status=swipe_status,
        platform=normalized_platform,
        query=normalized_query,
    )
    posts = [PostResponse.model_validate(row) for row in rows]
    has_more = total > (offset + limit)
    return PostListResponse(posts=posts, total=total, has_more=has_more)


@router.get("/posts/{classification_id}", response_model=PostResponse)
def get_post_detail(
    classification_id: str,
    db: Annotated[sqlite3.Connection, Depends(get_db)],
) -> PostResponse:
    row = get_post_for_feed_by_classification_id(conn=db, classification_id=classification_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")

    return PostResponse.model_validate(row)
