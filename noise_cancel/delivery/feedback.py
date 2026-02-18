from __future__ import annotations

import re
import sqlite3

from noise_cancel.models import Post


def parse_feedback_action(payload: dict) -> tuple[str, str] | None:
    """Parse a Slack interactive action payload.

    Return (feedback_type, post_id) or None if the payload is invalid.
    The expected action value format is "feedback_type|post_id".
    """
    actions = payload.get("actions")
    if not actions:
        return None

    first = actions[0]
    value = first.get("value")
    if not value or "|" not in value:
        return None

    parts = value.split("|", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return None

    return (parts[0], parts[1])


def should_auto_generate_rule(conn: sqlite3.Connection, post_id: str, threshold: int = 3) -> bool:
    """Check if mute_similar feedback count for a post reaches the threshold."""
    row = conn.execute(
        "SELECT COUNT(*) FROM user_feedback WHERE post_id = ? AND feedback_type = 'mute_similar'",
        (post_id,),
    ).fetchone()
    count = row[0] if row else 0
    return count >= threshold


def generate_mute_rule(post: Post, rule_name: str) -> dict:
    """Generate a mute rule dict from a post for auto-muting similar content.

    Extracts key patterns (significant words) from the post text.
    """
    # Extract meaningful words (4+ chars, lowercased, deduplicated)
    words = re.findall(r"[a-zA-Z]{4,}", post.post_text)
    # Lowercase and deduplicate while preserving order
    seen: set[str] = set()
    patterns: list[str] = []
    for w in words:
        lower = w.lower()
        if lower not in seen:
            seen.add(lower)
            patterns.append(lower)

    return {
        "rule_name": rule_name,
        "author_name": post.author_name,
        "patterns": patterns,
        "source_post_id": post.id,
    }
