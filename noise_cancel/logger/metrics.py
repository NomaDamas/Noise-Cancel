from __future__ import annotations

import sqlite3


def get_classification_stats(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute("SELECT category, COUNT(*) as cnt FROM classifications GROUP BY category").fetchall()
    return {row["category"]: row["cnt"] for row in rows}


def get_accuracy_stats(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute("SELECT feedback_type, COUNT(*) as cnt FROM user_feedback GROUP BY feedback_type").fetchall()
    result: dict[str, int] = {row["feedback_type"]: row["cnt"] for row in rows}
    result["total_feedback"] = sum(result.values())
    return result


def get_run_history(conn: sqlite3.Connection, limit: int = 10) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM run_logs ORDER BY started_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]
