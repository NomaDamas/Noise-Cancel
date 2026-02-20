from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

from noise_cancel.logger.export import export_csv, export_json
from noise_cancel.logger.metrics import (
    get_category_counts_for_window,
    get_classification_count_for_window,
    get_classification_details_for_window,
    get_classification_stats,
    get_classify_run_by_id,
    get_latest_classify_run,
    get_next_classify_run_started_at,
    get_run_history,
)
from noise_cancel.logger.repository import (
    get_classifications,
    get_posts,
    get_run_logs,
    get_unclassified_posts,
    get_undelivered_classifications,
    insert_classification,
    insert_post,
    insert_run_log,
    mark_delivered,
    update_run_log,
)
from noise_cancel.models import Classification, Post, RunLog

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run_log(run_id: str = "run-1", run_type: str = "full") -> RunLog:
    return RunLog(id=run_id, run_type=run_type, started_at="2025-01-01T00:00:00Z")


def _make_post(
    post_id: str = "post-1",
    author: str = "Alice",
    text: str = "Hello world",
    run_id: str | None = "run-1",
) -> Post:
    return Post(
        id=post_id,
        author_name=author,
        post_text=text,
        run_id=run_id,
        scraped_at="2025-01-01T00:00:00Z",
    )


def _make_classification(
    cls_id: str = "cls-1",
    post_id: str = "post-1",
    category: str = "Skip",
    confidence: float = 0.9,
    rules: list[str] | None = None,
) -> Classification:
    return Classification(
        id=cls_id,
        post_id=post_id,
        category=category,
        confidence=confidence,
        reasoning="test reasoning",
        applied_rules=rules or [],
        model_used="test-model",
        classified_at="2025-01-01T00:00:00Z",
    )


def _seed_basic(conn: sqlite3.Connection) -> None:
    """Insert a run_log, post, and classification for reuse."""
    insert_run_log(conn, _make_run_log())
    insert_post(conn, _make_post())
    insert_classification(conn, _make_classification())


# ---------------------------------------------------------------------------
# Repository -insert / get posts
# ---------------------------------------------------------------------------


class TestInsertAndGetPosts:
    def test_insert_and_retrieve_post(self, db_connection: sqlite3.Connection) -> None:
        insert_run_log(db_connection, _make_run_log())
        post = _make_post()
        insert_post(db_connection, post)

        rows = get_posts(db_connection)
        assert len(rows) == 1
        assert rows[0]["id"] == "post-1"
        assert rows[0]["author_name"] == "Alice"

    def test_get_posts_with_limit_and_offset(self, db_connection: sqlite3.Connection) -> None:
        insert_run_log(db_connection, _make_run_log())
        for i in range(5):
            insert_post(db_connection, _make_post(post_id=f"post-{i}", run_id="run-1"))

        rows = get_posts(db_connection, limit=2, offset=0)
        assert len(rows) == 2

        rows_offset = get_posts(db_connection, limit=10, offset=3)
        assert len(rows_offset) == 2

    def test_get_posts_filter_by_run_id(self, db_connection: sqlite3.Connection) -> None:
        insert_run_log(db_connection, _make_run_log("run-1"))
        insert_run_log(db_connection, _make_run_log("run-2"))
        insert_post(db_connection, _make_post(post_id="p1", run_id="run-1"))
        insert_post(db_connection, _make_post(post_id="p2", run_id="run-2"))

        rows = get_posts(db_connection, run_id="run-1")
        assert len(rows) == 1
        assert rows[0]["id"] == "p1"


# ---------------------------------------------------------------------------
# Repository -classifications
# ---------------------------------------------------------------------------


class TestClassifications:
    def test_insert_classification_with_applied_rules(self, db_connection: sqlite3.Connection) -> None:
        insert_run_log(db_connection, _make_run_log())
        insert_post(db_connection, _make_post())
        cls = _make_classification(rules=["rule-a", "rule-b"])
        insert_classification(db_connection, cls)

        rows = get_classifications(db_connection)
        assert len(rows) == 1
        rules = json.loads(rows[0]["applied_rules"])
        assert rules == ["rule-a", "rule-b"]

    def test_get_classifications_filter_by_category(self, db_connection: sqlite3.Connection) -> None:
        insert_run_log(db_connection, _make_run_log())
        insert_post(db_connection, _make_post("p1"))
        insert_post(db_connection, _make_post("p2"))
        insert_classification(db_connection, _make_classification("c1", "p1", "Skip"))
        insert_classification(db_connection, _make_classification("c2", "p2", "Read"))

        skip = get_classifications(db_connection, category="Skip")
        assert len(skip) == 1
        assert skip[0]["category"] == "Skip"

    def test_get_unclassified_posts(self, db_connection: sqlite3.Connection) -> None:
        insert_run_log(db_connection, _make_run_log())
        insert_post(db_connection, _make_post("p1"))
        insert_post(db_connection, _make_post("p2"))
        insert_classification(db_connection, _make_classification("c1", "p1"))

        unclassified = get_unclassified_posts(db_connection)
        assert len(unclassified) == 1
        assert unclassified[0]["id"] == "p2"

    def test_get_undelivered_classifications(self, db_connection: sqlite3.Connection) -> None:
        insert_run_log(db_connection, _make_run_log())
        insert_post(db_connection, _make_post("p1"))
        insert_post(db_connection, _make_post("p2"))
        insert_classification(db_connection, _make_classification("c1", "p1"))
        insert_classification(db_connection, _make_classification("c2", "p2"))
        mark_delivered(db_connection, "c1")

        undelivered = get_undelivered_classifications(db_connection)
        assert len(undelivered) == 1
        assert undelivered[0]["id"] == "c2"

    def test_mark_delivered_sets_timestamp(self, db_connection: sqlite3.Connection) -> None:
        _seed_basic(db_connection)
        mark_delivered(db_connection, "cls-1")

        rows = get_classifications(db_connection)
        assert rows[0]["delivered"] == 1
        assert rows[0]["delivered_at"] is not None


# ---------------------------------------------------------------------------
# Repository -run logs
# ---------------------------------------------------------------------------


class TestRunLogs:
    def test_insert_and_update_run_log(self, db_connection: sqlite3.Connection) -> None:
        rl = _make_run_log()
        insert_run_log(db_connection, rl)

        update_run_log(
            db_connection,
            "run-1",
            status="completed",
            posts_scraped=10,
            finished_at="2025-01-01T01:00:00Z",
        )

        row = db_connection.execute("SELECT * FROM run_logs WHERE id = ?", ("run-1",)).fetchone()
        assert row["status"] == "completed"
        assert row["posts_scraped"] == 10
        assert row["finished_at"] == "2025-01-01T01:00:00Z"

    def test_get_run_logs_orders_newest_first_and_respects_limit(self, db_connection: sqlite3.Connection) -> None:
        insert_run_log(db_connection, RunLog(id="run-1", run_type="scrape", started_at="2025-01-01T00:00:00Z"))
        insert_run_log(db_connection, RunLog(id="run-2", run_type="classify", started_at="2025-01-02T00:00:00Z"))
        insert_run_log(db_connection, RunLog(id="run-3", run_type="deliver", started_at="2025-01-03T00:00:00Z"))

        rows = get_run_logs(db_connection, limit=2)
        assert [row["id"] for row in rows] == ["run-3", "run-2"]

    def test_get_run_logs_filters_by_run_type_and_status(self, db_connection: sqlite3.Connection) -> None:
        insert_run_log(db_connection, RunLog(id="run-1", run_type="scrape", started_at="2025-01-01T00:00:00Z"))
        insert_run_log(db_connection, RunLog(id="run-2", run_type="classify", started_at="2025-01-02T00:00:00Z"))
        insert_run_log(db_connection, RunLog(id="run-3", run_type="scrape", started_at="2025-01-03T00:00:00Z"))
        update_run_log(db_connection, "run-1", status="completed")
        update_run_log(db_connection, "run-2", status="error")
        update_run_log(db_connection, "run-3", status="error")

        rows = get_run_logs(db_connection, run_type="scrape", status="error")
        assert len(rows) == 1
        assert rows[0]["id"] == "run-3"


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


class TestExport:
    def test_export_csv(self, db_connection: sqlite3.Connection, tmp_path: Path) -> None:
        _seed_basic(db_connection)
        out = str(tmp_path / "export.csv")
        export_csv(db_connection, out)

        with open(out, newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["post_id"] == "post-1"
        assert rows[0]["category"] == "Skip"

    def test_export_csv_filtered(self, db_connection: sqlite3.Connection, tmp_path: Path) -> None:
        insert_run_log(db_connection, _make_run_log())
        insert_post(db_connection, _make_post("p1"))
        insert_post(db_connection, _make_post("p2"))
        insert_classification(db_connection, _make_classification("c1", "p1", "Skip"))
        insert_classification(db_connection, _make_classification("c2", "p2", "Read"))

        out = str(tmp_path / "filtered.csv")
        export_csv(db_connection, out, category="Read")

        with open(out, newline="") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 1
        assert rows[0]["category"] == "Read"

    def test_export_json(self, db_connection: sqlite3.Connection, tmp_path: Path) -> None:
        _seed_basic(db_connection)
        out = str(tmp_path / "export.json")
        export_json(db_connection, out)

        with open(out) as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["post_id"] == "post-1"

    def test_export_json_filtered(self, db_connection: sqlite3.Connection, tmp_path: Path) -> None:
        insert_run_log(db_connection, _make_run_log())
        insert_post(db_connection, _make_post("p1"))
        insert_post(db_connection, _make_post("p2"))
        insert_classification(db_connection, _make_classification("c1", "p1", "Skip"))
        insert_classification(db_connection, _make_classification("c2", "p2", "Read"))

        out = str(tmp_path / "filtered.json")
        export_json(db_connection, out, category="Skip")

        with open(out) as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["category"] == "Skip"


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


class TestMetrics:
    def test_classification_stats(self, db_connection: sqlite3.Connection) -> None:
        insert_run_log(db_connection, _make_run_log())
        insert_post(db_connection, _make_post("p1"))
        insert_post(db_connection, _make_post("p2"))
        insert_post(db_connection, _make_post("p3"))
        insert_classification(db_connection, _make_classification("c1", "p1", "Skip"))
        insert_classification(db_connection, _make_classification("c2", "p2", "Skip"))
        insert_classification(db_connection, _make_classification("c3", "p3", "Read"))

        stats = get_classification_stats(db_connection)
        assert stats["Skip"] == 2
        assert stats["Read"] == 1

    def test_run_history(self, db_connection: sqlite3.Connection) -> None:
        for i in range(3):
            insert_run_log(db_connection, _make_run_log(f"run-{i}"))

        history = get_run_history(db_connection, limit=2)
        assert len(history) == 2

    def test_classification_stats_empty(self, db_connection: sqlite3.Connection) -> None:
        stats = get_classification_stats(db_connection)
        assert stats == {}

    def test_get_latest_classify_run(self, db_connection: sqlite3.Connection) -> None:
        insert_run_log(
            db_connection,
            RunLog(id="run-1", run_type="classify", started_at="2025-01-01T10:00:00"),
        )
        insert_run_log(
            db_connection,
            RunLog(id="run-2", run_type="classify", started_at="2025-01-01T11:00:00"),
        )

        row = get_latest_classify_run(db_connection)
        assert row is not None
        assert row["id"] == "run-2"

    def test_windowed_classification_helpers(self, db_connection: sqlite3.Connection) -> None:
        insert_run_log(db_connection, RunLog(id="run-a", run_type="classify", started_at="2025-01-01T10:00:00"))
        insert_run_log(db_connection, RunLog(id="run-b", run_type="classify", started_at="2025-01-01T11:00:00"))
        insert_run_log(db_connection, RunLog(id="seed", run_type="scrape"))
        insert_post(db_connection, _make_post("p1", run_id="run-a"))
        insert_post(db_connection, _make_post("p2", run_id="run-b"))
        insert_classification(
            db_connection,
            _make_classification("c1", "p1", "Skip").model_copy(update={"classified_at": "2025-01-01T10:30:00"}),
        )
        insert_classification(
            db_connection,
            _make_classification("c2", "p2", "Read").model_copy(update={"classified_at": "2025-01-01T11:30:00"}),
        )

        run_a = get_classify_run_by_id(db_connection, "run-a")
        assert run_a is not None
        boundary = get_next_classify_run_started_at(db_connection, run_a["started_at"], run_a["id"])
        assert boundary == "2025-01-01T11:00:00"

        rows = get_classification_details_for_window(db_connection, run_a["started_at"], boundary, limit=10)
        assert len(rows) == 1
        assert rows[0]["post_id"] == "p1"

        count = get_classification_count_for_window(db_connection, run_a["started_at"], boundary)
        assert count == 1
        categories = get_category_counts_for_window(db_connection, run_a["started_at"], boundary)
        assert categories == {"Skip": 1}
