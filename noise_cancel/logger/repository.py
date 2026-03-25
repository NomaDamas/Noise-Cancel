from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone

from noise_cancel.models import Classification, Post, RunLog


def insert_post(conn: sqlite3.Connection, post: Post) -> bool:
    """Insert a post row. Returns True if inserted, False if skipped (duplicate)."""
    d = post.to_dict()
    # OR IGNORE: duplicate post_url / content_hash rows are silently skipped
    # instead of raising IntegrityError.  Different platforms (RSS, Reddit,
    # LinkedIn) can legitimately produce overlapping URLs.
    cursor = conn.execute(
        """INSERT OR IGNORE INTO posts
           (id, platform, author_name, author_url, post_url, post_text,
            content_hash, media_type, post_timestamp, scraped_at, run_id,
            metadata)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
            json.dumps(d["metadata"]) if d.get("metadata") else None,
        ),
    )
    conn.commit()
    return cursor.rowcount > 0


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
_ALLOWED_SWIPE_STATUSES = frozenset({"pending", "archived", "deleted", "duplicate"})
_ALLOWED_BREAKDOWN_COLUMNS = frozenset({"platform", "category"})
_ALLOWED_FEEDBACK_ACTIONS = frozenset({"archive", "delete"})
_CONFIDENCE_BUCKETS: tuple[tuple[str, float], ...] = (
    ("0.0-0.2", 0.2),
    ("0.2-0.4", 0.4),
    ("0.4-0.6", 0.6),
    ("0.6-0.8", 0.8),
    ("0.8-1.0", 1.01),
)


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
    platform: str | None = None,
    query: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[dict]:
    sql = """SELECT
                 p.id AS id,
                 c.id AS classification_id,
                 p.platform,
                 p.author_name,
                 p.author_url,
                 p.post_url,
                 p.post_text,
                 c.summary,
                 c.category,
                 c.confidence,
                 c.reasoning,
                 c.classified_at,
                 c.swipe_status,
                 n.note_text AS note
             FROM classifications c
             INNER JOIN posts p ON p.id = c.post_id
             LEFT JOIN notes n ON n.classification_id = c.id"""
    where_clauses = ["c.category = ?", "c.swipe_status = ?"]
    params: list[object] = [category, swipe_status]

    if platform is not None:
        where_clauses.append("p.platform = ?")
        params.append(platform)

    if query is not None:
        escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        where_clauses.append("p.post_text LIKE ? ESCAPE '\\'")
        params.append(f"%{escaped}%")

    sql += " WHERE " + " AND ".join(where_clauses)
    sql += " ORDER BY c.classified_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def get_post_for_feed_by_classification_id(
    conn: sqlite3.Connection,
    classification_id: str,
) -> dict | None:
    row = conn.execute(
        """SELECT
               p.id AS id,
               c.id AS classification_id,
               p.platform,
               p.author_name,
               p.author_url,
               p.post_url,
               p.post_text,
               c.summary,
               c.category,
               c.confidence,
               c.reasoning,
               c.classified_at,
               c.swipe_status,
               n.note_text AS note
           FROM classifications c
           INNER JOIN posts p ON p.id = c.post_id
           LEFT JOIN notes n ON n.classification_id = c.id
           WHERE c.id = ?""",
        (classification_id,),
    ).fetchone()
    return dict(row) if row else None


def count_posts_for_feed(
    conn: sqlite3.Connection,
    category: str = "Read",
    swipe_status: str = "pending",
    platform: str | None = None,
    query: str | None = None,
) -> int:
    sql = """SELECT COUNT(*) AS total
             FROM classifications c
             INNER JOIN posts p ON p.id = c.post_id"""
    where_clauses = ["c.category = ?", "c.swipe_status = ?"]
    params: list[object] = [category, swipe_status]

    if platform is not None:
        where_clauses.append("p.platform = ?")
        params.append(platform)

    if query is not None:
        escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        where_clauses.append("p.post_text LIKE ? ESCAPE '\\'")
        params.append(f"%{escaped}%")

    sql += " WHERE " + " AND ".join(where_clauses)
    row = conn.execute(sql, params).fetchone()
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


def update_swipe_status(
    conn: sqlite3.Connection,
    classification_id: str,
    status: str,
    commit: bool = True,
) -> None:
    if status not in _ALLOWED_SWIPE_STATUSES:
        msg = f"Invalid swipe status: {status}"
        raise ValueError(msg)

    now = datetime.now(tz=timezone.utc).isoformat()
    conn.execute(
        "UPDATE classifications SET swipe_status = ?, swiped_at = ? WHERE id = ?",
        (status, now, classification_id),
    )
    if commit:
        conn.commit()


def insert_feedback(
    conn: sqlite3.Connection,
    classification_id: str,
    action: str,
    platform: str | None,
    category: str | None,
    confidence: float | None,
    commit: bool = True,
) -> dict:
    if action not in _ALLOWED_FEEDBACK_ACTIONS:
        msg = f"Invalid feedback action: {action}"
        raise ValueError(msg)

    feedback_id = uuid.uuid4().hex
    created_at = datetime.now(tz=timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO feedback
           (id, classification_id, action, platform, category, confidence, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (feedback_id, classification_id, action, platform, category, confidence, created_at),
    )
    if commit:
        conn.commit()
    row = conn.execute(
        """SELECT id, classification_id, action, platform, category, confidence, created_at
           FROM feedback
           WHERE id = ?""",
        (feedback_id,),
    ).fetchone()
    if row is None:
        msg = f"Failed to insert feedback id={feedback_id}"
        raise RuntimeError(msg)
    return dict(row)


def record_feedback_for_classification(
    conn: sqlite3.Connection,
    classification_id: str,
    action: str,
    commit: bool = True,
) -> dict | None:
    if action not in _ALLOWED_FEEDBACK_ACTIONS:
        msg = f"Invalid feedback action: {action}"
        raise ValueError(msg)

    row = conn.execute(
        """SELECT c.id AS classification_id, p.platform, c.category, c.confidence
           FROM classifications c
           INNER JOIN posts p ON p.id = c.post_id
           WHERE c.id = ?""",
        (classification_id,),
    ).fetchone()
    if row is None:
        return None

    return insert_feedback(
        conn=conn,
        classification_id=row["classification_id"],
        action=action,
        platform=row["platform"],
        category=row["category"],
        confidence=row["confidence"],
        commit=commit,
    )


def _ratio(count: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(count / total, 3)


def _build_feedback_breakdown(
    conn: sqlite3.Connection,
    label_column: str,
) -> list[dict]:
    if label_column not in _ALLOWED_BREAKDOWN_COLUMNS:
        msg = f"Invalid breakdown column: {label_column}"
        raise ValueError(msg)

    rows = conn.execute(
        f"""SELECT COALESCE({label_column}, 'unknown') AS label,
                   SUM(CASE WHEN action = 'archive' THEN 1 ELSE 0 END) AS archive_count,
                   SUM(CASE WHEN action = 'delete' THEN 1 ELSE 0 END) AS delete_count,
                   COUNT(*) AS total
            FROM feedback
            GROUP BY COALESCE({label_column}, 'unknown')
            ORDER BY label""",  # noqa: S608
    ).fetchall()

    payload: list[dict] = []
    for row in rows:
        total = int(row["total"])
        archive_count = int(row["archive_count"])
        delete_count = int(row["delete_count"])
        payload.append({
            "label": str(row["label"]),
            "archive_count": archive_count,
            "delete_count": delete_count,
            "total": total,
            "archive_ratio": _ratio(archive_count, total),
            "delete_ratio": _ratio(delete_count, total),
        })
    return payload


def _confidence_bucket(confidence: float) -> str:
    normalized = min(max(confidence, 0.0), 1.0)
    for label, upper_bound in _CONFIDENCE_BUCKETS:
        if normalized < upper_bound:
            return label
    return _CONFIDENCE_BUCKETS[-1][0]


def get_feedback_stats(conn: sqlite3.Connection) -> dict:
    total_row = conn.execute("SELECT COUNT(*) AS total FROM feedback").fetchone()
    total_feedback = int(total_row["total"]) if total_row else 0

    platform_rows = _build_feedback_breakdown(conn, "platform")
    by_platform = [
        {
            "platform": row["label"],
            "archive_count": row["archive_count"],
            "delete_count": row["delete_count"],
            "total": row["total"],
            "archive_ratio": row["archive_ratio"],
            "delete_ratio": row["delete_ratio"],
        }
        for row in platform_rows
    ]

    category_rows = _build_feedback_breakdown(conn, "category")
    by_category = [
        {
            "category": row["label"],
            "archive_count": row["archive_count"],
            "delete_count": row["delete_count"],
            "total": row["total"],
            "archive_ratio": row["archive_ratio"],
            "delete_ratio": row["delete_ratio"],
        }
        for row in category_rows
    ]

    override_rows = conn.execute(
        """SELECT confidence
           FROM feedback
           WHERE (action = 'delete' AND category = 'Read')
              OR (action = 'archive' AND category = 'Skip')""",
    ).fetchall()
    override_confidences = [float(row["confidence"]) for row in override_rows if row["confidence"] is not None]

    distribution_map = {label: 0 for label, _ in _CONFIDENCE_BUCKETS}
    for confidence in override_confidences:
        bucket = _confidence_bucket(confidence)
        distribution_map[bucket] += 1

    average_confidence: float | None = None
    if override_confidences:
        average_confidence = round(sum(override_confidences) / len(override_confidences), 3)

    return {
        "total_feedback": total_feedback,
        "by_platform": by_platform,
        "by_category": by_category,
        "override_confidence": {
            "total_overrides": len(override_confidences),
            "average_confidence": average_confidence,
            "distribution": [{"bucket": label, "count": distribution_map[label]} for label, _ in _CONFIDENCE_BUCKETS],
        },
    }


def get_note_by_classification_id(
    conn: sqlite3.Connection,
    classification_id: str,
) -> dict | None:
    row = conn.execute(
        """SELECT id, classification_id, note_text, created_at, updated_at
           FROM notes
           WHERE classification_id = ?""",
        (classification_id,),
    ).fetchone()
    return dict(row) if row else None


def upsert_note(conn: sqlite3.Connection, classification_id: str, note_text: str) -> dict:
    now = datetime.now(tz=timezone.utc).isoformat()
    existing = get_note_by_classification_id(conn, classification_id)
    note_id = existing["id"] if existing else uuid.uuid4().hex
    created_at = existing["created_at"] if existing else now
    conn.execute(
        """INSERT INTO notes (id, classification_id, note_text, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(classification_id) DO UPDATE SET
               note_text = excluded.note_text,
               updated_at = excluded.updated_at""",
        (note_id, classification_id, note_text, created_at, now),
    )
    conn.commit()
    note = get_note_by_classification_id(conn, classification_id)
    if note is None:
        msg = f"Failed to save note for classification_id={classification_id}"
        raise RuntimeError(msg)
    return note


def delete_note_by_classification_id(conn: sqlite3.Connection, classification_id: str) -> None:
    conn.execute(
        "DELETE FROM notes WHERE classification_id = ?",
        (classification_id,),
    )
    conn.commit()
