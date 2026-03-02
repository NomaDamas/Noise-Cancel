from __future__ import annotations

import inspect
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, cast

from noise_cancel.classifier.engine import ClassificationEngine
from noise_cancel.config import AppConfig
from noise_cancel.content_hash import compute_content_hash
from noise_cancel.dedup.embedder import create_embedder_from_config
from noise_cancel.dedup.semantic import ClaudeDuplicateVerifier, SemanticDeduplicator
from noise_cancel.delivery.notifier import notify_plugins
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


def _platform_display_name(platform: str) -> str:
    names = {
        "linkedin": "LinkedIn",
        "x": "X",
        "threads": "Threads",
        "reddit": "Reddit",
        "rss": "RSS",
    }
    return names.get(platform, platform.title())


def _session_warning_days(config: AppConfig, platform_config: dict[str, Any]) -> float:
    raw_warning_days = platform_config.get("session_warning_days", config.scraper.get("session_warning_days", 1))
    try:
        warning_days = float(raw_warning_days)
    except (TypeError, ValueError):
        return 1.0
    return max(0.0, warning_days)


def _warn_if_session_expiring(
    scraper: object,
    config: AppConfig,
    platform: str,
    platform_config: dict[str, Any],
) -> None:
    session_expires_in_days = getattr(scraper, "session_expires_in_days", None)
    if not callable(session_expires_in_days):
        return

    expires_in_days = session_expires_in_days()
    if expires_in_days is None or expires_in_days <= 0:
        return

    warning_days = _session_warning_days(config, platform_config)
    if expires_in_days > warning_days:
        return

    expires_in_hours = max(1, round(expires_in_days * 24))
    platform_name = _platform_display_name(platform)
    notify_plugins(
        f"⚠️ {platform_name} session expires in ~{expires_in_hours}h. "
        f"Run `noise-cancel login --platform {platform}` to refresh.",
        config,
        stderr_fallback=True,
    )


def _is_session_validation_failure(exc: RuntimeError) -> bool:
    error_message = str(exc).strip().lower()
    if "session" not in error_message:
        return False
    return any(
        marker in error_message
        for marker in (
            "expired",
            "invalid",
            "no session",
            "run login",
            "decrypt",
        )
    )


def _notify_expired_session(config: AppConfig, platform: str) -> None:
    platform_name = _platform_display_name(platform)
    notify_plugins(
        f"❌ {platform_name} session expired.",
        config,
        stderr_fallback=True,
    )


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


def _semantic_dedup_enabled(config: AppConfig) -> bool:
    dedup_config = config.dedup.get("semantic", {})
    return bool(dedup_config.get("enabled", False))


def _deduplicate_posts(
    conn: sqlite3.Connection,
    config: AppConfig,
    posts: list[Post],
) -> list[Post]:
    if not posts or not _semantic_dedup_enabled(config):
        return posts

    deduplicator = SemanticDeduplicator(
        conn=conn,
        config=config,
        embedder=create_embedder_from_config(config),
        verifier=ClaudeDuplicateVerifier(config).verify,
    )
    return deduplicator.deduplicate(posts)


async def _scrape_platform_posts(
    config: AppConfig,
    platform: str,
    platform_config: dict[str, Any],
) -> list[Post]:
    scraper_class = SCRAPER_REGISTRY.get(platform)
    scoped_config = _platform_scoped_config(config, platform_config)
    scraper = cast(Any, scraper_class)(scoped_config)
    try:
        _warn_if_session_expiring(scraper, scoped_config, platform, platform_config)

        scroll_count = int(platform_config.get("scroll_count", scoped_config.scraper.get("scroll_count", 10)))
        try:
            platform_posts = await scraper.scrape_feed(scroll_count=scroll_count)
        except RuntimeError as exc:
            if _is_session_validation_failure(exc):
                _notify_expired_session(scoped_config, platform)
            raise
    finally:
        await _close_scraper(scraper)

    for post in platform_posts:
        post.platform = platform
    return platform_posts


async def _scrape_posts(config: AppConfig) -> list[Post]:
    scraped_posts: list[Post] = []
    for platform, platform_config in _enabled_platform_configs(config):
        platform_posts = await _scrape_platform_posts(config, platform, platform_config)
        scraped_posts.extend(platform_posts)
    return scraped_posts


def _persist_scraped_posts(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    scraped_posts: list[Post],
    limit: int,
) -> list[Post]:
    posts_for_classification: list[Post] = []
    for post in scraped_posts[:limit]:
        post.run_id = run_id
        post.content_hash = compute_content_hash(post.post_text)
        try:
            insert_post(conn, post)
        except sqlite3.IntegrityError:
            continue
        posts_for_classification.append(post)
    return posts_for_classification


async def _prepare_posts_for_classification(
    conn: sqlite3.Connection,
    config: AppConfig,
    run_id: str,
    limit: int,
    skip_scrape: bool,
) -> tuple[list[Post], int]:
    if skip_scrape:
        rows = get_unclassified_posts(conn, limit=limit)
        return [Post(**row) for row in rows], 0

    scraped_posts = await _scrape_posts(config)
    posts_for_classification = _persist_scraped_posts(
        conn,
        run_id=run_id,
        scraped_posts=scraped_posts,
        limit=limit,
    )
    return posts_for_classification, len(posts_for_classification)


def _classify_posts(
    conn: sqlite3.Connection,
    config: AppConfig,
    posts_for_classification: list[Post],
) -> int:
    if not posts_for_classification:
        return 0

    engine = ClassificationEngine(config)
    results = engine.classify_posts(posts_for_classification)
    model_used = config.classifier.get("model", "unknown")
    posts_classified = 0

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
    return posts_classified


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
        posts_for_classification, posts_scraped = await _prepare_posts_for_classification(
            conn,
            config,
            run_id,
            limit,
            skip_scrape,
        )

        posts_for_classification = _deduplicate_posts(conn, config, posts_for_classification)
        posts_classified = _classify_posts(conn, config, posts_for_classification)

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
