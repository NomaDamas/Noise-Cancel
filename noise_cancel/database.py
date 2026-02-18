from __future__ import annotations

import sqlite3
from pathlib import Path

_MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations"


def get_connection(db_path: str) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def apply_migrations(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS _migrations (name TEXT PRIMARY KEY, applied_at TEXT DEFAULT (datetime('now')))"
    )

    if not _MIGRATIONS_DIR.exists():
        return

    migration_files = sorted(_MIGRATIONS_DIR.glob("*.sql"))
    applied = {row[0] for row in conn.execute("SELECT name FROM _migrations").fetchall()}

    for mf in migration_files:
        if mf.name not in applied:
            sql = mf.read_text()
            conn.executescript(sql)
            conn.execute("INSERT INTO _migrations (name) VALUES (?)", (mf.name,))
            conn.commit()
