from __future__ import annotations

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends

from noise_cancel.config import AppConfig
from noise_cancel.digest.service import generate_and_deliver_digest
from server.dependencies import get_config, get_db
from server.schemas import DigestGenerateResponse

router = APIRouter(tags=["digest"])


@router.post("/digest/generate", response_model=DigestGenerateResponse)
def generate_digest(
    db: Annotated[sqlite3.Connection, Depends(get_db)],
    config: Annotated[AppConfig, Depends(get_config)],
) -> DigestGenerateResponse:
    result = generate_and_deliver_digest(db, config)
    return DigestGenerateResponse(digest_text=result.digest_text)
