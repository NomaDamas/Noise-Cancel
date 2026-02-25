from __future__ import annotations

import inspect
import sqlite3
import uuid
from datetime import datetime, timezone

from noise_cancel.classifier.engine import ClassificationEngine
from noise_cancel.config import AppConfig
from noise_cancel.logger.repository import (
    get_unclassified_posts,
    insert_classification,
    insert_post,
    update_run_log,
)
from noise_cancel.models import Classification, Post
from noise_cancel.scraper.linkedin import LinkedInScraper


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _close_scraper(scraper: object) -> None:
    close = getattr(scraper, "close", None)
    if not callable(close):
        return

    close_result = close()
    if inspect.isawaitable(close_result):
        await close_result


async def run_pipeline(
    conn: sqlite3.Connection,
    config: AppConfig,
    run_id: str,
    limit: int,
    skip_scrape: bool,
) -> None:
    posts_scraped = 0
    posts_classified = 0

    try:
        posts_for_classification: list[Post]

        if skip_scrape:
            rows = get_unclassified_posts(conn, limit=limit)
            posts_for_classification = [Post(**row) for row in rows]
        else:
            scraper = LinkedInScraper(config)
            try:
                scroll_count = int(config.scraper.get("scroll_count", 10))
                scraped_posts = await scraper.scrape_feed(scroll_count=scroll_count)
            finally:
                await _close_scraper(scraper)

            posts_for_classification = []
            for post in scraped_posts[:limit]:
                post.run_id = run_id
                try:
                    insert_post(conn, post)
                except sqlite3.IntegrityError:
                    continue
                posts_for_classification.append(post)

            posts_scraped = len(posts_for_classification)

        if posts_for_classification:
            engine = ClassificationEngine(config)
            results = engine.classify_posts(posts_for_classification)
            model_used = config.classifier.get("model", "unknown")

            for result in results:
                classification = Classification(
                    id=uuid.uuid4().hex,
                    post_id=posts_for_classification[result.post_index].id,
                    category=result.category,
                    confidence=result.confidence,
                    reasoning=result.reasoning,
                    summary=result.summary,
                    applied_rules=result.applied_rules,
                    model_used=model_used,
                )
                try:
                    insert_classification(conn, classification)
                except sqlite3.IntegrityError:
                    continue
                posts_classified += 1

        update_run_log(
            conn,
            run_id,
            finished_at=_now_iso(),
            status="completed",
            posts_scraped=posts_scraped,
            posts_classified=posts_classified,
        )
    except Exception as exc:
        update_run_log(
            conn,
            run_id,
            finished_at=_now_iso(),
            status="error",
            posts_scraped=posts_scraped,
            posts_classified=posts_classified,
            error_message=str(exc),
        )
