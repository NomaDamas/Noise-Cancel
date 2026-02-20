from __future__ import annotations

import sqlite3


def get_classification_stats(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute("SELECT category, COUNT(*) as cnt FROM classifications GROUP BY category").fetchall()
    return {row["category"]: row["cnt"] for row in rows}


def get_run_history(conn: sqlite3.Connection, limit: int = 10) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM run_logs ORDER BY started_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_latest_classify_run(conn: sqlite3.Connection) -> dict | None:
    row = conn.execute(
        """SELECT * FROM run_logs
           WHERE run_type = 'classify'
           ORDER BY started_at DESC, id DESC
           LIMIT 1"""
    ).fetchone()
    return dict(row) if row else None


def get_classify_run_by_id(conn: sqlite3.Connection, run_id: str) -> dict | None:
    row = conn.execute(
        """SELECT * FROM run_logs
           WHERE id = ? AND run_type = 'classify'
           LIMIT 1""",
        (run_id,),
    ).fetchone()
    return dict(row) if row else None


def get_next_classify_run_started_at(conn: sqlite3.Connection, started_at: str, run_id: str) -> str | None:
    row = conn.execute(
        """SELECT started_at FROM run_logs
           WHERE run_type = 'classify'
             AND (started_at > ? OR (started_at = ? AND id > ?))
           ORDER BY started_at ASC, id ASC
           LIMIT 1""",
        (started_at, started_at, run_id),
    ).fetchone()
    return row["started_at"] if row else None


def get_classification_details_for_window(
    conn: sqlite3.Connection,
    started_at: str,
    end_before: str | None = None,
    limit: int = 50,
) -> list[dict]:
    if end_before is None:
        rows = conn.execute(
            """SELECT c.id AS classification_id, c.post_id, c.category, c.confidence,
                      c.reasoning, c.classified_at, p.author_name, p.post_text, p.post_url
               FROM classifications c
               JOIN posts p ON p.id = c.post_id
               WHERE c.classified_at >= ?
               ORDER BY c.classified_at DESC
               LIMIT ?""",
            (started_at, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT c.id AS classification_id, c.post_id, c.category, c.confidence,
                      c.reasoning, c.classified_at, p.author_name, p.post_text, p.post_url
               FROM classifications c
               JOIN posts p ON p.id = c.post_id
               WHERE c.classified_at >= ? AND c.classified_at < ?
               ORDER BY c.classified_at DESC
               LIMIT ?""",
            (started_at, end_before, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def get_classification_count_for_window(
    conn: sqlite3.Connection,
    started_at: str,
    end_before: str | None = None,
) -> int:
    if end_before is None:
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM classifications WHERE classified_at >= ?",
            (started_at,),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT COUNT(*) AS cnt FROM classifications WHERE classified_at >= ? AND classified_at < ?",
            (started_at, end_before),
        ).fetchone()
    return int(row["cnt"]) if row else 0


def get_category_counts_for_window(
    conn: sqlite3.Connection,
    started_at: str,
    end_before: str | None = None,
) -> dict[str, int]:
    if end_before is None:
        rows = conn.execute(
            """SELECT category, COUNT(*) AS cnt
               FROM classifications
               WHERE classified_at >= ?
               GROUP BY category
               ORDER BY cnt DESC, category ASC""",
            (started_at,),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT category, COUNT(*) AS cnt
               FROM classifications
               WHERE classified_at >= ? AND classified_at < ?
               GROUP BY category
               ORDER BY cnt DESC, category ASC""",
            (started_at, end_before),
        ).fetchall()
    return {row["category"]: row["cnt"] for row in rows}
