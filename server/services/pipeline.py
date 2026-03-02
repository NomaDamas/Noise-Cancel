from __future__ import annotations

import inspect
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, cast

from noise_cancel.classifier.engine import ClassificationEngine
from noise_cancel.config import AppConfig
from noise_cancel.content_hash import compute_content_hash
from noise_cancel.logger.repository import (
    get_unclassified_posts,
    insert_classification,
    insert_post,
    update_run_log,
)
from noise_cancel.models import Classification, Post
from noise_cancel.scraper.registry import SCRAPER_REGISTRY


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _close_scraper(scraper: object) -> None:
    close = getattr(scraper, "close", None)
    if not callable(close):
        return

    close_result = close()
    if inspect.isawaitable(close_result):
        await close_result


def _enabled_platform_configs(config: AppConfig) -> list[tuple[str, dict[str, Any]]]:
    platforms = config.scraper.get("platforms", {})
    if not isinstance(platforms, dict):
        return []

    enabled: list[tuple[str, dict[str, Any]]] = []
    for platform, platform_config in platforms.items():
        if not isinstance(platform, str) or not platform.strip():
            continue
        if not isinstance(platform_config, dict):
            continue
        if not bool(platform_config.get("enabled", True)):
            continue
        enabled.append((platform.strip().lower(), platform_config))
    return enabled


def _platform_scoped_config(
    config: AppConfig,
    platform_config: dict[str, Any],
) -> AppConfig:
    scoped = config.model_copy(deep=True)
    merged_scraper = {k: v for k, v in scoped.scraper.items() if k != "platforms"}
    merged_scraper.update(platform_config)
    merged_scraper["platforms"] = config.scraper.get("platforms", {})
    scoped.scraper = merged_scraper
    return scoped


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
            enabled_platforms = _enabled_platform_configs(config)
            scraped_posts: list[Post] = []

            for platform, platform_config in enabled_platforms:
                scraper_class = SCRAPER_REGISTRY.get(platform)
                scoped_config = _platform_scoped_config(config, platform_config)
                scraper = cast(Any, scraper_class)(scoped_config)
                try:
                    scroll_count = int(
                        platform_config.get("scroll_count", scoped_config.scraper.get("scroll_count", 10))
                    )
                    platform_posts = await scraper.scrape_feed(scroll_count=scroll_count)
                finally:
                    await _close_scraper(scraper)

                for post in platform_posts:
                    post.platform = platform
                scraped_posts.extend(platform_posts)

            posts_for_classification = []
            for post in scraped_posts[:limit]:
                post.run_id = run_id
                post.content_hash = compute_content_hash(post.post_text)
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
