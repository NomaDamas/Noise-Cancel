import sqlite3

import pytest

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
    expected = {"posts", "classifications", "run_logs", "embeddings", "notes"}
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
    assert "content_hash" in columns
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
    assert "007_add_notes.sql" in applied
    conn.close()


def test_embeddings_table_columns(db_connection):
    cursor = db_connection.execute("PRAGMA table_info(embeddings)")
    columns = {row[1] for row in cursor.fetchall()}
    assert columns == {"post_id", "vector", "model", "created_at"}


def test_notes_table_columns(db_connection):
    cursor = db_connection.execute("PRAGMA table_info(notes)")
    columns = {row[1] for row in cursor.fetchall()}
    assert columns == {"id", "classification_id", "note_text", "created_at", "updated_at"}


def test_posts_content_hash_index_unique_allows_null(db_connection):
    db_connection.execute(
        "INSERT INTO posts (id, platform, author_name, post_text, scraped_at) VALUES (?, ?, ?, ?, ?)",
        ("p1", "linkedin", "Alice", "A", "2025-01-01T00:00:00"),
    )
    db_connection.execute(
        "INSERT INTO posts (id, platform, author_name, post_text, scraped_at) VALUES (?, ?, ?, ?, ?)",
        ("p2", "linkedin", "Bob", "B", "2025-01-01T00:00:00"),
    )
    db_connection.commit()

    db_connection.execute(
        "INSERT INTO posts (id, platform, author_name, post_text, scraped_at, content_hash) VALUES (?, ?, ?, ?, ?, ?)",
        ("p3", "linkedin", "Carol", "C", "2025-01-01T00:00:00", "same-hash"),
    )
    db_connection.commit()

    with pytest.raises(sqlite3.IntegrityError):
        db_connection.execute(
            "INSERT INTO posts (id, platform, author_name, post_text, scraped_at, content_hash)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            ("p4", "linkedin", "Dave", "D", "2025-01-01T00:00:00", "same-hash"),
        )


def test_posts_platform_rejects_unknown_value(db_connection):
    with pytest.raises(sqlite3.IntegrityError):
        db_connection.execute(
            "INSERT INTO posts (id, platform, author_name, post_text, scraped_at) VALUES (?, ?, ?, ?, ?)",
            ("bad-platform-post", "myspace", "Eve", "Invalid platform", "2025-01-01T00:00:00"),
        )
