from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from noise_cancel.models import Classification, Post, RunLog


def insert_post(conn: sqlite3.Connection, post: Post) -> None:
    d = post.to_dict()
    conn.execute(
        """INSERT INTO posts
           (id, platform, author_name, author_url, post_url, post_text,
            content_hash, media_type, post_timestamp, scraped_at, run_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            d["id"],
            d["platform"],
            d["author_name"],
            d["author_url"],
            d["post_url"],
            d["post_text"],
            d["content_hash"],
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
_ALLOWED_SWIPE_STATUSES = frozenset({"pending", "archived", "deleted"})


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


def get_run_logs(
    conn: sqlite3.Connection,
    limit: int = 20,
    run_type: str | None = None,
    status: str | None = None,
) -> list[dict]:
    sql = "SELECT * FROM run_logs"
    where_clauses: list[str] = []
    params: list[object] = []

    if run_type is not None:
        where_clauses.append("run_type = ?")
        params.append(run_type)
    if status is not None:
        where_clauses.append("status = ?")
        params.append(status)

    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)

    sql += " ORDER BY started_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


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


def get_posts_for_feed(
    conn: sqlite3.Connection,
    category: str = "Read",
    swipe_status: str = "pending",
    limit: int = 20,
    offset: int = 0,
) -> list[dict]:
    rows = conn.execute(
        """SELECT
               p.id AS id,
               c.id AS classification_id,
               p.author_name,
               p.author_url,
               p.post_url,
               p.post_text,
               c.summary,
               c.category,
               c.confidence,
               c.reasoning,
               c.classified_at,
               c.swipe_status
           FROM classifications c
           INNER JOIN posts p ON p.id = c.post_id
           WHERE c.category = ? AND c.swipe_status = ?
           ORDER BY c.classified_at DESC
           LIMIT ? OFFSET ?""",
        (category, swipe_status, limit, offset),
    ).fetchall()
    return [dict(r) for r in rows]


def get_post_for_feed_by_classification_id(
    conn: sqlite3.Connection,
    classification_id: str,
) -> dict | None:
    row = conn.execute(
        """SELECT
               p.id AS id,
               c.id AS classification_id,
               p.author_name,
               p.author_url,
               p.post_url,
               p.post_text,
               c.summary,
               c.category,
               c.confidence,
               c.reasoning,
               c.classified_at,
               c.swipe_status
           FROM classifications c
           INNER JOIN posts p ON p.id = c.post_id
           WHERE c.id = ?""",
        (classification_id,),
    ).fetchone()
    return dict(row) if row else None


def count_posts_for_feed(
    conn: sqlite3.Connection,
    category: str = "Read",
    swipe_status: str = "pending",
) -> int:
    row = conn.execute(
        """SELECT COUNT(*) AS total
           FROM classifications c
           INNER JOIN posts p ON p.id = c.post_id
           WHERE c.category = ? AND c.swipe_status = ?""",
        (category, swipe_status),
    ).fetchone()
    return int(row["total"]) if row else 0


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


def mark_delivered(conn: sqlite3.Connection, classification_id: str) -> None:
    now = datetime.now(tz=timezone.utc).isoformat()
    conn.execute(
        "UPDATE classifications SET delivered = 1, delivered_at = ? WHERE id = ?",
        (now, classification_id),
    )
    conn.commit()


def update_swipe_status(conn: sqlite3.Connection, classification_id: str, status: str) -> None:
    if status not in _ALLOWED_SWIPE_STATUSES:
        msg = f"Invalid swipe status: {status}"
        raise ValueError(msg)

    now = datetime.now(tz=timezone.utc).isoformat()
    conn.execute(
        "UPDATE classifications SET swipe_status = ?, swiped_at = ? WHERE id = ?",
        (status, now, classification_id),
    )
    conn.commit()
