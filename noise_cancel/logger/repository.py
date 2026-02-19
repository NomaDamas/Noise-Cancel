from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from noise_cancel.models import Classification, Post, RunLog, UserFeedback


def insert_post(conn: sqlite3.Connection, post: Post) -> None:
    d = post.to_dict()
    conn.execute(
        """INSERT INTO posts
           (id, platform, author_name, author_url, post_url, post_text,
            media_type, post_timestamp, scraped_at, run_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            d["id"],
            d["platform"],
            d["author_name"],
            d["author_url"],
            d["post_url"],
            d["post_text"],
            d["media_type"],
            d["post_timestamp"],
            d["scraped_at"],
            d["run_id"],
        ),
    )
    conn.commit()


def insert_classification(conn: sqlite3.Connection, classification: Classification) -> None:
    d = classification.to_dict()
    conn.execute(
        """INSERT INTO classifications
           (id, post_id, category, confidence, reasoning, summary, applied_rules,
            model_used, classified_at, delivered, delivered_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            d["id"],
            d["post_id"],
            d["category"],
            d["confidence"],
            d["reasoning"],
            d["summary"],
            json.dumps(d["applied_rules"]),
            d["model_used"],
            d["classified_at"],
            d["delivered"],
            d["delivered_at"],
        ),
    )
    conn.commit()


def insert_feedback(conn: sqlite3.Connection, feedback: UserFeedback) -> None:
    d = feedback.to_dict()
    conn.execute(
        """INSERT INTO user_feedback
           (id, post_id, classification_id, feedback_type, source, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            d["id"],
            d["post_id"],
            d["classification_id"],
            d["feedback_type"],
            d["source"],
            d["created_at"],
        ),
    )
    conn.commit()


def insert_run_log(conn: sqlite3.Connection, run_log: RunLog) -> None:
    d = run_log.to_dict()
    conn.execute(
        """INSERT INTO run_logs
           (id, run_type, started_at, finished_at, status,
            posts_scraped, posts_classified, posts_delivered, error_message)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            d["id"],
            d["run_type"],
            d["started_at"],
            d["finished_at"],
            d["status"],
            d["posts_scraped"],
            d["posts_classified"],
            d["posts_delivered"],
            d["error_message"],
        ),
    )
    conn.commit()


_ALLOWED_RUN_LOG_COLUMNS = frozenset({
    "finished_at",
    "status",
    "posts_scraped",
    "posts_classified",
    "posts_delivered",
    "error_message",
})


def update_run_log(conn: sqlite3.Connection, run_id: str, **kwargs: object) -> None:
    if not kwargs:
        return
    for k in kwargs:
        if k not in _ALLOWED_RUN_LOG_COLUMNS:
            msg = f"Invalid column: {k}"
            raise ValueError(msg)
    set_clauses = [f"{k} = ?" for k in kwargs]
    values = list(kwargs.values())
    values.append(run_id)
    conn.execute(
        f"UPDATE run_logs SET {', '.join(set_clauses)} WHERE id = ?",  # noqa: S608
        values,
    )
    conn.commit()


def get_post_by_id(conn: sqlite3.Connection, post_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    return dict(row) if row else None


def get_posts(
    conn: sqlite3.Connection,
    limit: int = 50,
    offset: int = 0,
    run_id: str | None = None,
) -> list[dict]:
    if run_id is not None:
        rows = conn.execute(
            "SELECT * FROM posts WHERE run_id = ? LIMIT ? OFFSET ?",
            (run_id, limit, offset),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM posts LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return [dict(r) for r in rows]


def get_unclassified_posts(conn: sqlite3.Connection, limit: int = 50) -> list[dict]:
    rows = conn.execute(
        """SELECT p.* FROM posts p
           LEFT JOIN classifications c ON p.id = c.post_id
           WHERE c.id IS NULL
           LIMIT ?""",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_undelivered_classifications(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM classifications WHERE delivered = 0").fetchall()
    return [dict(r) for r in rows]


def get_classifications(
    conn: sqlite3.Connection,
    category: str | None = None,
    limit: int = 50,
) -> list[dict]:
    if category is not None:
        rows = conn.execute(
            "SELECT * FROM classifications WHERE category = ? LIMIT ?",
            (category, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM classifications LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_feedback_for_post(conn: sqlite3.Connection, post_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM user_feedback WHERE post_id = ?",
        (post_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def mark_delivered(conn: sqlite3.Connection, classification_id: str) -> None:
    now = datetime.now(tz=timezone.utc).isoformat()
    conn.execute(
        "UPDATE classifications SET delivered = 1, delivered_at = ? WHERE id = ?",
        (now, classification_id),
    )
    conn.commit()


def get_feedback_counts(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute("SELECT feedback_type, COUNT(*) as cnt FROM user_feedback GROUP BY feedback_type").fetchall()
    return {row["feedback_type"]: row["cnt"] for row in rows}
