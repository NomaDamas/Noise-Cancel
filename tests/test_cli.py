from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from typer.testing import CliRunner

from noise_cancel.cli import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_config(tmp_path: Path) -> tuple[Path, Path]:
    """Write a minimal config YAML and return (config_path, data_dir)."""
    data_dir = tmp_path / "data"
    config_path = tmp_path / "config.yaml"
    config_path.write_text(f"general:\n  data_dir: {data_dir}\n")
    return config_path, data_dir


def _mock_scraper(storage_state: dict | None = None) -> MagicMock:
    """Create a mock LinkedInScraper instance with the given storage state."""
    mock = MagicMock()
    mock.login = AsyncMock()
    mock.storage_state = storage_state
    return mock


def _create_session(data_dir: Path) -> None:
    """Create a valid encrypted session in data_dir for scrape tests."""
    from noise_cancel.scraper.auth import generate_key, save_session

    data_dir.mkdir(parents=True, exist_ok=True)
    key = generate_key()
    (data_dir / "session.key").write_text(key)
    save_session({"cookies": [{"name": "li_at", "value": "tok"}]}, key, str(data_dir / "session.enc"))


def test_app_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "noise-cancel" in result.output.lower() or "Usage" in result.output


def test_config_command():
    result = runner.invoke(app, ["config"])
    assert result.exit_code == 0


def test_init_creates_config(tmp_path: Path):
    out = tmp_path / "config.yaml"
    result = runner.invoke(app, ["init", "--config", str(out)])
    assert result.exit_code == 0
    assert out.exists()
    content = out.read_text()
    assert "classifier:" in content
    assert "claude-sonnet-4-6" in content
    assert "Read" in content
    assert "Skip" in content


def test_init_refuses_overwrite(tmp_path: Path):
    out = tmp_path / "config.yaml"
    out.write_text("existing")
    result = runner.invoke(app, ["init", "--config", str(out)])
    assert result.exit_code == 1
    assert "already exists" in result.output
    # Original content preserved
    assert out.read_text() == "existing"


# ===========================================================================
# Login command tests
# ===========================================================================


class TestLoginCommand:
    def test_login_saves_session_and_key(self, tmp_path: Path):
        config_path, data_dir = _write_config(tmp_path)
        mock_storage = {"cookies": [{"name": "li_at", "value": "abc123"}]}
        mock = _mock_scraper(storage_state=mock_storage)

        with patch("noise_cancel.scraper.linkedin.LinkedInScraper", return_value=mock):
            result = runner.invoke(app, ["login", "--config", str(config_path)])

        assert result.exit_code == 0
        assert "Login successful" in result.output
        assert (data_dir / "session.enc").exists()
        assert (data_dir / "session.key").exists()

    def test_login_session_is_decryptable(self, tmp_path: Path):
        from noise_cancel.scraper.auth import load_session

        config_path, data_dir = _write_config(tmp_path)
        mock_storage = {"cookies": [{"name": "li_at", "value": "secret"}]}
        mock = _mock_scraper(storage_state=mock_storage)

        with patch("noise_cancel.scraper.linkedin.LinkedInScraper", return_value=mock):
            runner.invoke(app, ["login", "--config", str(config_path)])

        key = (data_dir / "session.key").read_text().strip()
        loaded = load_session(key, str(data_dir / "session.enc"))
        assert loaded == mock_storage

    def test_login_reuses_existing_key(self, tmp_path: Path):
        from noise_cancel.scraper.auth import generate_key

        config_path, data_dir = _write_config(tmp_path)
        data_dir.mkdir(parents=True, exist_ok=True)
        existing_key = generate_key()
        (data_dir / "session.key").write_text(existing_key)

        mock = _mock_scraper(storage_state={"cookies": []})

        with patch("noise_cancel.scraper.linkedin.LinkedInScraper", return_value=mock):
            result = runner.invoke(app, ["login", "--config", str(config_path)])

        assert result.exit_code == 0
        # Key file should still contain the original key
        assert (data_dir / "session.key").read_text().strip() == existing_key

    def test_login_fails_when_no_session_captured(self, tmp_path: Path):
        config_path, _ = _write_config(tmp_path)
        mock = _mock_scraper(storage_state=None)

        with patch("noise_cancel.scraper.linkedin.LinkedInScraper", return_value=mock):
            result = runner.invoke(app, ["login", "--config", str(config_path)])

        assert result.exit_code == 1
        assert "Login failed" in result.output

    def test_login_key_file_permissions(self, tmp_path: Path):
        config_path, data_dir = _write_config(tmp_path)
        mock = _mock_scraper(storage_state={"cookies": []})

        with patch("noise_cancel.scraper.linkedin.LinkedInScraper", return_value=mock):
            runner.invoke(app, ["login", "--config", str(config_path)])

        key_stat = (data_dir / "session.key").stat()
        # Owner read/write only (0o600)
        assert oct(key_stat.st_mode)[-3:] == "600"


# ===========================================================================
# Scrape command tests
# ===========================================================================


def _mock_feed_scraper(posts: list | None = None) -> MagicMock:
    """Create a mock LinkedInScraper for scrape_feed testing."""

    mock = MagicMock()
    mock.load_storage_state = MagicMock()
    mock.scrape_feed = AsyncMock(return_value=posts or [])
    return mock


class TestScrapeCommand:
    def test_scrape_saves_posts_to_db(self, tmp_path: Path):
        from noise_cancel.database import apply_migrations, get_connection
        from noise_cancel.models import Post

        config_path, data_dir = _write_config(tmp_path)
        _create_session(data_dir)

        posts = [
            Post(id="p1", author_name="Alice", post_text="Hello", post_url="https://li.com/p1"),
            Post(id="p2", author_name="Bob", post_text="World", post_url="https://li.com/p2"),
        ]
        mock = _mock_feed_scraper(posts)

        with patch("noise_cancel.scraper.linkedin.LinkedInScraper", return_value=mock):
            result = runner.invoke(app, ["scrape", "--config", str(config_path)])

        assert result.exit_code == 0
        assert "Scraped 2 posts" in result.output

        # Verify posts in DB
        conn = get_connection(str(data_dir / "noise_cancel.db"))
        apply_migrations(conn)
        rows = conn.execute("SELECT id FROM posts").fetchall()
        assert {r["id"] for r in rows} == {"p1", "p2"}
        conn.close()

    def test_scrape_creates_run_log(self, tmp_path: Path):
        from noise_cancel.database import apply_migrations, get_connection
        from noise_cancel.models import Post

        config_path, data_dir = _write_config(tmp_path)
        _create_session(data_dir)

        posts = [Post(id="p1", author_name="Alice", post_text="Hi", post_url="https://li.com/p1")]
        mock = _mock_feed_scraper(posts)

        with patch("noise_cancel.scraper.linkedin.LinkedInScraper", return_value=mock):
            result = runner.invoke(app, ["scrape", "--config", str(config_path)])

        assert result.exit_code == 0

        conn = get_connection(str(data_dir / "noise_cancel.db"))
        apply_migrations(conn)
        rows = conn.execute("SELECT * FROM run_logs WHERE run_type = 'scrape'").fetchall()
        assert len(rows) == 1
        assert rows[0]["status"] == "completed"
        assert rows[0]["posts_scraped"] == 1
        conn.close()

    def test_scrape_fails_without_session(self, tmp_path: Path):
        config_path, _ = _write_config(tmp_path)
        result = runner.invoke(app, ["scrape", "--config", str(config_path)])
        assert result.exit_code == 1
        assert "No session found" in result.output

    def test_scrape_handles_expired_session(self, tmp_path: Path):
        import os
        import time

        config_path, data_dir = _write_config(tmp_path)
        _create_session(data_dir)

        # Backdate session file by 8 days
        session_path = str(data_dir / "session.enc")
        old_time = time.time() - (8 * 86400)
        os.utime(session_path, (old_time, old_time))

        result = runner.invoke(app, ["scrape", "--config", str(config_path)])
        assert result.exit_code == 1
        assert "Session expired" in result.output


# ===========================================================================
# Helpers for classify/deliver tests
# ===========================================================================


def _seed_db(tmp_path: Path) -> tuple[Path, Path]:
    """Write config, create DB with migrations, and return (config_path, data_dir)."""
    config_path, data_dir = _write_config(tmp_path)
    data_dir.mkdir(parents=True, exist_ok=True)
    return config_path, data_dir


def _insert_post(conn, post_id: str = "p1", author: str = "Alice", text: str = "Hello world") -> None:
    """Insert a minimal post row via raw SQL."""
    conn.execute(
        "INSERT INTO posts (id, platform, author_name, post_text, scraped_at) VALUES (?, ?, ?, ?, ?)",
        (post_id, "linkedin", author, text, "2025-01-01T00:00:00"),
    )
    conn.commit()


def _insert_classification(
    conn,
    cls_id: str = "c1",
    post_id: str = "p1",
    category: str = "Read",
    delivered: int = 0,
) -> None:
    """Insert a minimal classification row via raw SQL."""
    import json

    conn.execute(
        """INSERT INTO classifications
           (id, post_id, category, confidence, reasoning, applied_rules,
            model_used, classified_at, delivered, delivered_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            cls_id,
            post_id,
            category,
            0.9,
            "test reason",
            json.dumps([]),
            "test-model",
            "2025-01-01T00:00:00",
            delivered,
            None,
        ),
    )
    conn.commit()


def _insert_run_log(
    conn,
    run_id: str,
    run_type: str,
    started_at: str,
    finished_at: str | None = None,
    status: str = "running",
    posts_scraped: int = 0,
    posts_classified: int = 0,
    posts_delivered: int = 0,
    error_message: str | None = None,
) -> None:
    """Insert a run_log row via raw SQL for logs command testing."""
    conn.execute(
        """INSERT INTO run_logs
           (id, run_type, started_at, finished_at, status,
            posts_scraped, posts_classified, posts_delivered, error_message)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            run_id,
            run_type,
            started_at,
            finished_at,
            status,
            posts_scraped,
            posts_classified,
            posts_delivered,
            error_message,
        ),
    )
    conn.commit()


# ===========================================================================
# Classify command tests
# ===========================================================================


class TestClassifyCommand:
    def test_classify_processes_unclassified_posts(self, tmp_path: Path):
        from noise_cancel.classifier.schemas import PostClassification
        from noise_cancel.database import apply_migrations, get_connection

        config_path, data_dir = _seed_db(tmp_path)

        # Pre-create DB and seed a post
        conn = get_connection(str(data_dir / "noise_cancel.db"))
        apply_migrations(conn)
        _insert_post(conn, "p1", "Alice", "Great insights on AI")
        conn.close()

        mock_results = [
            PostClassification(post_index=0, category="Read", confidence=0.95, reasoning="Relevant AI content"),
        ]

        with patch("noise_cancel.classifier.engine.ClassificationEngine.classify_posts", return_value=mock_results):
            result = runner.invoke(app, ["classify", "--config", str(config_path)])

        assert result.exit_code == 0
        assert "Classified 1 posts" in result.output

        conn = get_connection(str(data_dir / "noise_cancel.db"))
        apply_migrations(conn)
        rows = conn.execute("SELECT * FROM classifications").fetchall()
        assert len(rows) == 1
        assert rows[0]["post_id"] == "p1"
        assert rows[0]["category"] == "Read"
        conn.close()

    def test_classify_creates_run_log(self, tmp_path: Path):
        from noise_cancel.classifier.schemas import PostClassification
        from noise_cancel.database import apply_migrations, get_connection

        config_path, data_dir = _seed_db(tmp_path)

        conn = get_connection(str(data_dir / "noise_cancel.db"))
        apply_migrations(conn)
        _insert_post(conn, "p1")
        conn.close()

        mock_results = [
            PostClassification(post_index=0, category="Skip", confidence=0.8, reasoning="Spam"),
        ]

        with patch("noise_cancel.classifier.engine.ClassificationEngine.classify_posts", return_value=mock_results):
            result = runner.invoke(app, ["classify", "--config", str(config_path)])

        assert result.exit_code == 0

        conn = get_connection(str(data_dir / "noise_cancel.db"))
        apply_migrations(conn)
        rows = conn.execute("SELECT * FROM run_logs WHERE run_type = 'classify'").fetchall()
        assert len(rows) == 1
        assert rows[0]["status"] == "completed"
        assert rows[0]["posts_classified"] == 1
        conn.close()

    def test_classify_no_unclassified_posts(self, tmp_path: Path):
        config_path, data_dir = _seed_db(tmp_path)

        # Create DB with no posts
        from noise_cancel.database import apply_migrations, get_connection

        conn = get_connection(str(data_dir / "noise_cancel.db"))
        apply_migrations(conn)
        conn.close()

        result = runner.invoke(app, ["classify", "--config", str(config_path)])
        assert result.exit_code == 0
        assert "No unclassified posts" in result.output

    def test_classify_dry_run_does_not_insert(self, tmp_path: Path):
        from noise_cancel.classifier.schemas import PostClassification
        from noise_cancel.database import apply_migrations, get_connection

        config_path, data_dir = _seed_db(tmp_path)

        conn = get_connection(str(data_dir / "noise_cancel.db"))
        apply_migrations(conn)
        _insert_post(conn, "p1", "Alice", "Some post")
        conn.close()

        mock_results = [
            PostClassification(post_index=0, category="Read", confidence=0.9, reasoning="Good stuff"),
        ]

        with patch("noise_cancel.classifier.engine.ClassificationEngine.classify_posts", return_value=mock_results):
            result = runner.invoke(app, ["classify", "--config", str(config_path), "--dry-run"])

        assert result.exit_code == 0
        assert "Dry run" in result.output

        conn = get_connection(str(data_dir / "noise_cancel.db"))
        apply_migrations(conn)
        rows = conn.execute("SELECT * FROM classifications").fetchall()
        assert len(rows) == 0
        conn.close()

    def test_classify_handles_engine_error(self, tmp_path: Path):
        from noise_cancel.database import apply_migrations, get_connection

        config_path, data_dir = _seed_db(tmp_path)

        conn = get_connection(str(data_dir / "noise_cancel.db"))
        apply_migrations(conn)
        _insert_post(conn, "p1")
        conn.close()

        with patch(
            "noise_cancel.classifier.engine.ClassificationEngine.classify_posts",
            side_effect=RuntimeError("API timeout"),
        ):
            result = runner.invoke(app, ["classify", "--config", str(config_path)])

        assert result.exit_code == 1
        assert "Classification failed" in result.output

        conn = get_connection(str(data_dir / "noise_cancel.db"))
        apply_migrations(conn)
        rows = conn.execute("SELECT * FROM run_logs WHERE run_type = 'classify'").fetchall()
        assert len(rows) == 1
        assert rows[0]["status"] == "error"
        conn.close()


# ===========================================================================
# Deliver command tests
# ===========================================================================


class TestDeliverCommand:
    def test_deliver_sends_to_slack(self, tmp_path: Path):
        from noise_cancel.database import apply_migrations, get_connection

        config_path, data_dir = _seed_db(tmp_path)

        conn = get_connection(str(data_dir / "noise_cancel.db"))
        apply_migrations(conn)
        _insert_post(conn, "p1", "Alice", "Great post")
        _insert_classification(conn, "c1", "p1", "Read", delivered=0)
        conn.close()

        with patch("noise_cancel.delivery.slack.deliver_posts", return_value=1) as mock_deliver:
            result = runner.invoke(app, ["deliver", "--config", str(config_path)])

        assert result.exit_code == 0
        assert "Delivered 1 posts" in result.output
        mock_deliver.assert_called_once()

        # Verify classification marked as delivered
        conn = get_connection(str(data_dir / "noise_cancel.db"))
        apply_migrations(conn)
        row = conn.execute("SELECT delivered FROM classifications WHERE id = 'c1'").fetchone()
        assert row["delivered"] == 1
        conn.close()

    def test_deliver_creates_run_log(self, tmp_path: Path):
        from noise_cancel.database import apply_migrations, get_connection

        config_path, data_dir = _seed_db(tmp_path)

        conn = get_connection(str(data_dir / "noise_cancel.db"))
        apply_migrations(conn)
        _insert_post(conn, "p1", "Alice", "Post")
        _insert_classification(conn, "c1", "p1", "Read", delivered=0)
        conn.close()

        with patch("noise_cancel.delivery.slack.deliver_posts", return_value=1):
            result = runner.invoke(app, ["deliver", "--config", str(config_path)])

        assert result.exit_code == 0

        conn = get_connection(str(data_dir / "noise_cancel.db"))
        apply_migrations(conn)
        rows = conn.execute("SELECT * FROM run_logs WHERE run_type = 'deliver'").fetchall()
        assert len(rows) == 1
        assert rows[0]["status"] == "completed"
        assert rows[0]["posts_delivered"] == 1
        conn.close()

    def test_deliver_no_undelivered(self, tmp_path: Path):
        from noise_cancel.database import apply_migrations, get_connection

        config_path, data_dir = _seed_db(tmp_path)

        conn = get_connection(str(data_dir / "noise_cancel.db"))
        apply_migrations(conn)
        conn.close()

        result = runner.invoke(app, ["deliver", "--config", str(config_path)])
        assert result.exit_code == 0
        assert "No undelivered classifications" in result.output

    def test_deliver_skips_already_delivered(self, tmp_path: Path):
        from noise_cancel.database import apply_migrations, get_connection

        config_path, data_dir = _seed_db(tmp_path)

        conn = get_connection(str(data_dir / "noise_cancel.db"))
        apply_migrations(conn)
        _insert_post(conn, "p1", "Alice", "Post")
        _insert_classification(conn, "c1", "p1", "Read", delivered=1)
        conn.close()

        result = runner.invoke(app, ["deliver", "--config", str(config_path)])
        assert result.exit_code == 0
        assert "No undelivered classifications" in result.output


# ===========================================================================
# Logs command tests
# ===========================================================================


class TestLogsCommand:
    def test_logs_shows_run_history_table(self, tmp_path: Path):
        from noise_cancel.database import apply_migrations, get_connection

        config_path, data_dir = _seed_db(tmp_path)
        conn = get_connection(str(data_dir / "noise_cancel.db"))
        apply_migrations(conn)
        _insert_run_log(
            conn,
            run_id="run-1",
            run_type="scrape",
            started_at="2025-01-01T00:00:00Z",
            finished_at="2025-01-01T00:00:30Z",
            status="completed",
            posts_scraped=3,
        )
        conn.close()

        result = runner.invoke(app, ["logs", "--config", str(config_path)])

        assert result.exit_code == 0
        assert "Run Logs" in result.output
        assert "┏" in result.output

    def test_logs_limit(self, tmp_path: Path):
        from noise_cancel.database import apply_migrations, get_connection

        config_path, data_dir = _seed_db(tmp_path)
        conn = get_connection(str(data_dir / "noise_cancel.db"))
        apply_migrations(conn)
        _insert_run_log(conn, "run-old", "scrape", "2025-01-01T00:00:00Z")
        _insert_run_log(conn, "run-new", "scrape", "2025-01-02T00:00:00Z")
        conn.close()

        result = runner.invoke(app, ["logs", "--config", str(config_path), "--limit", "1", "--json"])

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert len(payload) == 1
        assert payload[0]["run_id"] == "run-new"

    def test_logs_filters_by_run_type(self, tmp_path: Path):
        from noise_cancel.database import apply_migrations, get_connection

        config_path, data_dir = _seed_db(tmp_path)
        conn = get_connection(str(data_dir / "noise_cancel.db"))
        apply_migrations(conn)
        _insert_run_log(conn, "run-scrape", "scrape", "2025-01-01T00:00:00Z")
        _insert_run_log(conn, "run-classify", "classify", "2025-01-02T00:00:00Z")
        conn.close()

        result = runner.invoke(app, ["logs", "--config", str(config_path), "--run-type", "scrape", "--json"])

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert len(payload) == 1
        assert payload[0]["run_id"] == "run-scrape"

    def test_logs_filters_by_status(self, tmp_path: Path):
        from noise_cancel.database import apply_migrations, get_connection

        config_path, data_dir = _seed_db(tmp_path)
        conn = get_connection(str(data_dir / "noise_cancel.db"))
        apply_migrations(conn)
        _insert_run_log(conn, "run-ok", "scrape", "2025-01-01T00:00:00Z", status="completed")
        _insert_run_log(conn, "run-err", "scrape", "2025-01-02T00:00:00Z", status="error")
        conn.close()

        result = runner.invoke(app, ["logs", "--config", str(config_path), "--status", "error", "--json"])

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert len(payload) == 1
        assert payload[0]["run_id"] == "run-err"

    def test_logs_json_output_omits_finished_and_duration(self, tmp_path: Path):
        from noise_cancel.database import apply_migrations, get_connection

        config_path, data_dir = _seed_db(tmp_path)
        conn = get_connection(str(data_dir / "noise_cancel.db"))
        apply_migrations(conn)
        _insert_run_log(
            conn,
            run_id="run-1",
            run_type="scrape",
            started_at="2025-01-01T00:00:00Z",
            finished_at="2025-01-01T00:00:30Z",
            status="completed",
            posts_scraped=1,
        )
        conn.close()

        result = runner.invoke(app, ["logs", "--config", str(config_path), "--json"])

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert len(payload) == 1
        assert payload[0]["run_id"] == "run-1"
        assert payload[0]["started_at"] == "2025-01-01T00:00:00Z"
        assert "finished_at" not in payload[0]
        assert "duration_s" not in payload[0]

    def test_logs_json_non_applicable_counts_are_null(self, tmp_path: Path):
        from noise_cancel.database import apply_migrations, get_connection

        config_path, data_dir = _seed_db(tmp_path)
        conn = get_connection(str(data_dir / "noise_cancel.db"))
        apply_migrations(conn)
        _insert_run_log(
            conn,
            run_id="run-c",
            run_type="classify",
            started_at="2025-01-01T00:00:00Z",
            status="completed",
            posts_scraped=99,
            posts_classified=2,
            posts_delivered=99,
        )
        conn.close()

        result = runner.invoke(app, ["logs", "--config", str(config_path), "--json"])

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert len(payload) == 1
        assert payload[0]["run_type"] == "classify"
        assert payload[0]["posts_classified"] == 2
        assert payload[0]["posts_scraped"] is None
        assert payload[0]["posts_delivered"] is None

    def test_logs_handles_empty_history(self, tmp_path: Path):
        from noise_cancel.database import apply_migrations, get_connection

        config_path, data_dir = _seed_db(tmp_path)
        conn = get_connection(str(data_dir / "noise_cancel.db"))
        apply_migrations(conn)
        conn.close()

        result = runner.invoke(app, ["logs", "--config", str(config_path)])

        assert result.exit_code == 0
        assert "No run logs found." in result.output


# ===========================================================================
# Run (pipeline) command tests
# ===========================================================================


class TestRunCommand:
    def test_run_executes_full_pipeline(self, tmp_path: Path):
        from noise_cancel.classifier.schemas import PostClassification
        from noise_cancel.database import apply_migrations, get_connection
        from noise_cancel.models import Post

        config_path, data_dir = _write_config(tmp_path)
        _create_session(data_dir)

        posts = [Post(id="p1", author_name="Alice", post_text="Hello", post_url="https://li.com/p1")]
        mock_scraper = _mock_feed_scraper(posts)
        mock_cls = [PostClassification(post_index=0, category="Read", confidence=0.9, reasoning="Good")]

        with (
            patch("noise_cancel.scraper.linkedin.LinkedInScraper", return_value=mock_scraper),
            patch("noise_cancel.classifier.engine.ClassificationEngine.classify_posts", return_value=mock_cls),
            patch("noise_cancel.delivery.slack.deliver_posts", return_value=1),
        ):
            result = runner.invoke(app, ["run", "--config", str(config_path)])

        assert result.exit_code == 0
        assert "Pipeline complete" in result.output

        conn = get_connection(str(data_dir / "noise_cancel.db"))
        apply_migrations(conn)
        rows = conn.execute("SELECT * FROM run_logs WHERE run_type = 'pipeline'").fetchall()
        assert len(rows) == 1
        assert rows[0]["status"] == "completed"
        conn.close()

    def test_run_stops_on_scrape_failure(self, tmp_path: Path):
        from noise_cancel.database import apply_migrations, get_connection

        config_path, data_dir = _seed_db(tmp_path)
        # No session → scrape will fail
        data_dir.mkdir(parents=True, exist_ok=True)
        # Pre-create DB so pipeline run_log can be written
        conn = get_connection(str(data_dir / "noise_cancel.db"))
        apply_migrations(conn)
        conn.close()

        result = runner.invoke(app, ["run", "--config", str(config_path)])

        assert result.exit_code == 1
        assert "Pipeline stopped at scrape" in result.output

        conn = get_connection(str(data_dir / "noise_cancel.db"))
        apply_migrations(conn)
        rows = conn.execute("SELECT * FROM run_logs WHERE run_type = 'pipeline'").fetchall()
        assert len(rows) == 1
        assert rows[0]["status"] == "error"
        conn.close()

    def test_run_dry_run_skips_deliver(self, tmp_path: Path):
        from noise_cancel.classifier.schemas import PostClassification
        from noise_cancel.models import Post

        config_path, data_dir = _write_config(tmp_path)
        _create_session(data_dir)

        posts = [Post(id="p1", author_name="Alice", post_text="Hello", post_url="https://li.com/p1")]
        mock_scraper = _mock_feed_scraper(posts)
        mock_cls = [PostClassification(post_index=0, category="Read", confidence=0.9, reasoning="Good")]

        with (
            patch("noise_cancel.scraper.linkedin.LinkedInScraper", return_value=mock_scraper),
            patch("noise_cancel.classifier.engine.ClassificationEngine.classify_posts", return_value=mock_cls),
            patch("noise_cancel.delivery.slack.deliver_posts", return_value=0) as mock_deliver,
        ):
            result = runner.invoke(app, ["run", "--config", str(config_path), "--dry-run"])

        assert result.exit_code == 0
        assert "Pipeline complete" in result.output
        mock_deliver.assert_not_called()
