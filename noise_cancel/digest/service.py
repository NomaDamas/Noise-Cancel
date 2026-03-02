from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from importlib import import_module

from pydantic import BaseModel, Field

from noise_cancel.config import AppConfig
from noise_cancel.delivery.loader import get_delivery_plugin_class

_SYSTEM_PROMPT = """You are an editor writing a daily social-feed digest.
Summarize the provided Read-classified posts from multiple platforms.
Return concise, concrete output suitable for a daily briefing.
"""


class DailyDigestSummary(BaseModel):
    themes: list[str] = Field(default_factory=list)
    notable_posts: list[str] = Field(default_factory=list)


@dataclass
class DigestRunResult:
    digest_text: str
    delivered_plugins: int
    delivery_enabled: bool


def _normalize_now(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc)


def _recent_read_posts(conn: sqlite3.Connection, *, since_iso: str) -> list[dict]:
    rows = conn.execute(
        """SELECT
               p.platform,
               p.author_name,
               p.post_url,
               p.post_text,
               c.summary,
               c.classified_at
           FROM classifications c
           INNER JOIN posts p ON p.id = c.post_id
           WHERE c.category = 'Read'
             AND c.classified_at >= ?
           ORDER BY c.classified_at DESC""",
        (since_iso,),
    ).fetchall()
    return [dict(row) for row in rows]


def _category_counts(conn: sqlite3.Connection, *, since_iso: str) -> dict[str, int]:
    rows = conn.execute(
        """SELECT category, COUNT(*) AS cnt
           FROM classifications
           WHERE classified_at >= ?
           GROUP BY category""",
        (since_iso,),
    ).fetchall()
    return {row["category"]: int(row["cnt"]) for row in rows}


def _platform_breakdown(read_posts: list[dict]) -> dict[str, int]:
    breakdown: dict[str, int] = {}
    for row in read_posts:
        platform = row.get("platform")
        if not isinstance(platform, str) or not platform.strip():
            continue
        key = platform.strip().lower()
        breakdown[key] = breakdown.get(key, 0) + 1

    # Stable deterministic order for text output.
    return dict(sorted(breakdown.items(), key=lambda item: (-item[1], item[0])))


def _normalize_line(value: object, *, max_len: int = 240) -> str:
    if not isinstance(value, str):
        return ""
    line = " ".join(value.split()).strip()
    if len(line) <= max_len:
        return line
    return line[: max_len - 3].rstrip() + "..."


def _build_user_prompt(
    *,
    date_label: str,
    read_posts: list[dict],
    platform_breakdown: dict[str, int],
    saved_count: int,
    filtered_count: int,
) -> str:
    lines = [
        f"Date: {date_label}",
        "Generate a cross-platform daily digest from these Read posts.",
        "",
        "Platform breakdown:",
    ]
    if platform_breakdown:
        for platform, count in platform_breakdown.items():
            lines.append(f"- {platform}: {count}")
    else:
        lines.append("- none: 0")

    lines.extend(["", f"Stats: saved={saved_count}, filtered={filtered_count}", "", "Posts:"])

    for index, row in enumerate(read_posts, start=1):
        summary = _normalize_line(row.get("summary"))
        text = _normalize_line(row.get("post_text"), max_len=400)
        lines.extend([
            f"{index}. [{row.get('platform', 'unknown')}] {row.get('author_name', 'Unknown author')}",
            f"   summary: {summary or '(none)'}",
            f"   text: {text or '(none)'}",
        ])

    lines.extend([
        "",
        "Return 3-5 theme bullets and a short list of notable posts.",
    ])
    return "\n".join(lines)


def _normalize_bullets(items: list[str], *, min_items: int, max_items: int, fallback: list[str]) -> list[str]:
    cleaned = [_normalize_line(item) for item in items]
    cleaned = [item for item in cleaned if item]

    for fallback_item in fallback:
        if len(cleaned) >= min_items:
            break
        normalized = _normalize_line(fallback_item)
        if normalized and normalized not in cleaned:
            cleaned.append(normalized)

    if not cleaned:
        cleaned.append("No major patterns identified.")

    return cleaned[:max_items]


def _fallback_themes(read_posts: list[dict]) -> list[str]:
    themes: list[str] = []
    for row in read_posts[:5]:
        platform = row.get("platform", "unknown")
        summary = _normalize_line(row.get("summary")) or _normalize_line(row.get("post_text"), max_len=140)
        if summary:
            themes.append(f"{platform}: {summary}")
    return themes


def _fallback_notable_posts(read_posts: list[dict]) -> list[str]:
    notable: list[str] = []
    for row in read_posts[:5]:
        platform = row.get("platform", "unknown")
        author = _normalize_line(row.get("author_name"), max_len=80) or "Unknown author"
        summary = _normalize_line(row.get("summary")) or _normalize_line(row.get("post_text"), max_len=140)
        if summary:
            notable.append(f"{platform}: {author} — {summary}")
    return notable


def _generate_structured_summary(
    config: AppConfig,
    *,
    user_prompt: str,
) -> DailyDigestSummary:
    digest_config = config.delivery.get("digest", {})
    model = config.classifier.get("model", "claude-sonnet-4-6")
    temperature = 0.0

    if isinstance(digest_config, dict):
        configured_model = digest_config.get("model")
        if isinstance(configured_model, str) and configured_model.strip():
            model = configured_model

        configured_temperature = digest_config.get("temperature")
        if isinstance(configured_temperature, (int, float)):
            temperature = float(configured_temperature)

    anthropic = import_module("anthropic")
    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=2048,
        temperature=temperature,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
        tools=[
            {
                "name": "write_digest",
                "description": "Write a structured daily digest summary.",
                "input_schema": DailyDigestSummary.model_json_schema(),
            }
        ],
        tool_choice={"type": "tool", "name": "write_digest"},
    )

    for block in response.content:
        if getattr(block, "type", None) != "tool_use":
            continue

        block_input = getattr(block, "input", None)
        if isinstance(block_input, dict):
            return DailyDigestSummary.model_validate(block_input)

    return DailyDigestSummary()


def _format_digest_text(
    *,
    date_label: str,
    platform_breakdown: dict[str, int],
    themes: list[str],
    notable_posts: list[str],
    saved_count: int,
    filtered_count: int,
) -> str:
    lines = [
        "Daily Feed Digest",
        f"Date: {date_label}",
        "",
        "Platform breakdown:",
    ]
    if platform_breakdown:
        for platform, count in platform_breakdown.items():
            lines.append(f"- {platform}: {count}")
    else:
        lines.append("- none: 0")

    lines.extend(["", "Theme summary:"])
    for theme in themes:
        lines.append(f"- {theme}")

    lines.extend(["", "Notable posts:"])
    for notable in notable_posts:
        lines.append(f"- {notable}")

    lines.extend([
        "",
        "Total stats:",
        f"- saved: {saved_count}",
        f"- filtered: {filtered_count}",
    ])
    return "\n".join(lines)


def generate_daily_digest(
    conn: sqlite3.Connection,
    config: AppConfig,
    *,
    now: datetime | None = None,
) -> str:
    now_utc = _normalize_now(now)
    since_utc = now_utc - timedelta(hours=24)
    since_iso = since_utc.isoformat()
    date_label = now_utc.date().isoformat()

    read_posts = _recent_read_posts(conn, since_iso=since_iso)
    platform_breakdown = _platform_breakdown(read_posts)
    counts = _category_counts(conn, since_iso=since_iso)
    saved_count = counts.get("Read", 0)
    filtered_count = counts.get("Skip", 0)

    if not read_posts:
        return _format_digest_text(
            date_label=date_label,
            platform_breakdown=platform_breakdown,
            themes=["No Read posts found in the last 24 hours."],
            notable_posts=["No notable Read posts in this window."],
            saved_count=saved_count,
            filtered_count=filtered_count,
        )

    user_prompt = _build_user_prompt(
        date_label=date_label,
        read_posts=read_posts,
        platform_breakdown=platform_breakdown,
        saved_count=saved_count,
        filtered_count=filtered_count,
    )
    summary = _generate_structured_summary(config, user_prompt=user_prompt)

    themes = _normalize_bullets(
        summary.themes,
        min_items=3,
        max_items=5,
        fallback=_fallback_themes(read_posts),
    )
    notable_posts = _normalize_bullets(
        summary.notable_posts,
        min_items=1,
        max_items=5,
        fallback=_fallback_notable_posts(read_posts),
    )

    return _format_digest_text(
        date_label=date_label,
        platform_breakdown=platform_breakdown,
        themes=themes,
        notable_posts=notable_posts,
        saved_count=saved_count,
        filtered_count=filtered_count,
    )


def _digest_delivery_enabled(config: AppConfig) -> bool:
    digest_config = config.delivery.get("digest", {})
    if not isinstance(digest_config, dict):
        return True
    return bool(digest_config.get("enabled", True))


def deliver_digest_with_plugins(
    digest_text: str,
    config: AppConfig,
) -> int:
    delivered = 0
    plugins = config.delivery.get("plugins", [])
    for plugin_config in plugins:
        if not isinstance(plugin_config, dict):
            continue

        plugin_type = plugin_config.get("type")
        if not isinstance(plugin_type, str) or not plugin_type.strip():
            continue

        plugin_class = get_delivery_plugin_class(plugin_type)
        plugin = plugin_class()
        plugin.validate_config(plugin_config)
        delivered += int(plugin.deliver_digest(digest_text, config, plugin_config))
    return delivered


def generate_and_deliver_digest(
    conn: sqlite3.Connection,
    config: AppConfig,
    *,
    now: datetime | None = None,
) -> DigestRunResult:
    digest_text = generate_daily_digest(conn, config, now=now)
    delivery_enabled = _digest_delivery_enabled(config)
    delivered_plugins = 0
    if delivery_enabled:
        delivered_plugins = deliver_digest_with_plugins(digest_text, config)

    return DigestRunResult(
        digest_text=digest_text,
        delivered_plugins=delivered_plugins,
        delivery_enabled=delivery_enabled,
    )
