from __future__ import annotations

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends

from noise_cancel.logger.repository import get_feedback_stats
from server.dependencies import get_db
from server.schemas import FeedbackStatsResponse

router = APIRouter(tags=["feedback"])


@router.get("/feedback/stats", response_model=FeedbackStatsResponse)
def feedback_stats(
    db: Annotated[sqlite3.Connection, Depends(get_db)],
) -> FeedbackStatsResponse:
    payload = get_feedback_stats(db)
    return FeedbackStatsResponse.model_validate(payload)
