from __future__ import annotations

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from noise_cancel.logger.repository import (
    get_post_for_feed_by_classification_id,
    record_feedback_for_classification,
    update_swipe_status,
)
from server.dependencies import get_db
from server.schemas import ArchivePostResponse, DeleteResponse

router = APIRouter(tags=["actions"])


@router.post("/posts/{classification_id}/archive", response_model=ArchivePostResponse)
def archive_post(
    classification_id: str,
    db: Annotated[sqlite3.Connection, Depends(get_db)],
) -> ArchivePostResponse:
    post = get_post_for_feed_by_classification_id(conn=db, classification_id=classification_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Not found")

    update_swipe_status(conn=db, classification_id=classification_id, status="archived")
    record_feedback_for_classification(conn=db, classification_id=classification_id, action="archive")

    return ArchivePostResponse(
        status="archived",
        classification_id=classification_id,
        author_name=post["author_name"],
        summary=post["summary"],
        post_url=post["post_url"],
        post_text=post["post_text"],
        category=post["category"],
    )


@router.post("/posts/{classification_id}/delete", response_model=DeleteResponse)
def delete_post(
    classification_id: str,
    db: Annotated[sqlite3.Connection, Depends(get_db)],
) -> DeleteResponse:
    post = get_post_for_feed_by_classification_id(conn=db, classification_id=classification_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Not found")

    update_swipe_status(conn=db, classification_id=classification_id, status="deleted")
    record_feedback_for_classification(conn=db, classification_id=classification_id, action="delete")

    return DeleteResponse(status="deleted", classification_id=classification_id)
