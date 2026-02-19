import sqlite3

from noise_cancel.database import apply_migrations, get_connection


def test_get_connection(tmp_path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    assert isinstance(conn, sqlite3.Connection)
    conn.close()


def test_apply_migrations(tmp_path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    apply_migrations(conn)

    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = {row[0] for row in cursor.fetchall()}
    expected = {"posts", "classifications", "run_logs"}
    assert expected.issubset(tables)
    conn.close()


def test_migrations_idempotent(tmp_path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    apply_migrations(conn)
    apply_migrations(conn)  # Should not raise
    conn.close()


def test_posts_table_columns(db_connection):
    cursor = db_connection.execute("PRAGMA table_info(posts)")
    columns = {row[1] for row in cursor.fetchall()}
    assert "id" in columns
    assert "author_name" in columns
    assert "post_text" in columns
    assert "post_url" in columns
    assert "scraped_at" in columns


def test_classifications_table_columns(db_connection):
    cursor = db_connection.execute("PRAGMA table_info(classifications)")
    columns = {row[1] for row in cursor.fetchall()}
    assert "post_id" in columns
    assert "category" in columns
    assert "confidence" in columns
    assert "reasoning" in columns
    assert "delivered" in columns
