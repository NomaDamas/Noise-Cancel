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
    assert "swipe_status" in columns
    assert "swiped_at" in columns


def test_classifications_swipe_status_default_and_not_null(db_connection):
    rows = db_connection.execute("PRAGMA table_info(classifications)").fetchall()
    by_name = {row[1]: row for row in rows}
    swipe_status_column = by_name["swipe_status"]

    # PRAGMA table_info layout: (cid, name, type, notnull, dflt_value, pk)
    assert swipe_status_column[3] == 1
    assert str(swipe_status_column[4]).strip("'\"") == "pending"


def test_classifications_swipe_indexes_exist(db_connection):
    rows = db_connection.execute("PRAGMA index_list(classifications)").fetchall()
    index_names = {row[1] for row in rows}

    assert "idx_classifications_swipe" in index_names
    assert "idx_classifications_category" in index_names

    swipe_columns = {row[2] for row in db_connection.execute("PRAGMA index_info(idx_classifications_swipe)").fetchall()}
    category_columns = {
        row[2] for row in db_connection.execute("PRAGMA index_info(idx_classifications_category)").fetchall()
    }
    assert swipe_columns == {"swipe_status"}
    assert category_columns == {"category"}


def test_apply_migrations_tracks_latest_migration(tmp_path):
    db_path = tmp_path / "test.db"
    conn = get_connection(str(db_path))
    apply_migrations(conn)

    applied = {row[0] for row in conn.execute("SELECT name FROM _migrations").fetchall()}
    assert "003_add_swipe_status.sql" in applied
    conn.close()
