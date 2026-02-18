from __future__ import annotations

import csv
import json
import sqlite3


def _query_posts_with_classifications(
    conn: sqlite3.Connection,
    category: str | None = None,
) -> list[dict]:
    sql = """
        SELECT p.id AS post_id, p.author_name, p.post_text, p.post_url,
               p.scraped_at, c.category, c.confidence, c.reasoning,
               c.applied_rules, c.model_used, c.classified_at
        FROM posts p
        JOIN classifications c ON p.id = c.post_id
    """
    params: list[object] = []
    if category is not None:
        sql += " WHERE c.category = ?"
        params.append(category)
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def export_csv(
    conn: sqlite3.Connection,
    output_path: str,
    category: str | None = None,
) -> None:
    rows = _query_posts_with_classifications(conn, category)
    if not rows:
        with open(output_path, "w", newline="") as f:
            f.write("")
        return

    fieldnames = list(rows[0].keys())
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def export_json(
    conn: sqlite3.Connection,
    output_path: str,
    category: str | None = None,
) -> None:
    rows = _query_posts_with_classifications(conn, category)
    with open(output_path, "w") as f:
        json.dump(rows, f, indent=2)
