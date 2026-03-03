from __future__ import annotations

import sqlite3
import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from noise_cancel.config import AppConfig
from noise_cancel.logger.repository import get_run_logs, insert_run_log
from noise_cancel.models import RunLog
from server.dependencies import get_config, get_db
from server.schemas import PipelineRunRequest, PipelineRunResponse, PipelineStatusResponse
from server.services.pipeline import run_pipeline

router = APIRouter(tags=["pipeline"])


@router.post("/pipeline/run", response_model=PipelineRunResponse, status_code=202)
def run_pipeline_endpoint(
    background_tasks: BackgroundTasks,
    db: Annotated[sqlite3.Connection, Depends(get_db)],
    config: Annotated[AppConfig, Depends(get_config)],
    request: PipelineRunRequest | None = None,
) -> PipelineRunResponse:
    recent_runs = get_run_logs(db, limit=1)
    if recent_runs and recent_runs[0]["status"] == "running":
        raise HTTPException(
            status_code=409,
            detail=f"Pipeline already running (run_id: {recent_runs[0]['id']})",
        )

    payload = request or PipelineRunRequest()

    run_id = uuid.uuid4().hex
    insert_run_log(db, RunLog(id=run_id, run_type="pipeline"))

    background_tasks.add_task(
        run_pipeline,
        config,
        run_id,
        payload.limit,
        payload.skip_scrape,
    )

    return PipelineRunResponse(
        run_id=run_id,
        status="accepted",
        message="Pipeline run started",
    )


@router.get("/pipeline/status", response_model=PipelineStatusResponse)
def get_pipeline_status(
    db: Annotated[sqlite3.Connection, Depends(get_db)],
) -> PipelineStatusResponse:
    rows = get_run_logs(db, limit=1)
    if not rows:
        raise HTTPException(status_code=404, detail="Not found")

    latest = rows[0]
    return PipelineStatusResponse(
        run_id=latest["id"],
        run_type=latest["run_type"],
        started_at=latest["started_at"],
        finished_at=latest["finished_at"],
        status=latest["status"],
        posts_scraped=latest["posts_scraped"],
        posts_classified=latest["posts_classified"],
        posts_delivered=latest["posts_delivered"],
        error_message=latest["error_message"],
    )
