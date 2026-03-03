from __future__ import annotations

import csv
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

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
    count_posts_for_feed,
    delete_note_by_classification_id,
    get_classifications,
    get_feedback_stats,
    get_note_by_classification_id,
    get_posts,
    get_posts_for_feed,
    get_run_logs,
    get_unclassified_posts,
    get_undelivered_classifications,
    insert_classification,
    insert_post,
    insert_run_log,
    mark_delivered,
    record_feedback_for_classification,
    update_run_log,
    update_swipe_status,
    upsert_note,
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
    platform: str = "linkedin",
) -> Post:
    return Post(
        id=post_id,
        platform=platform,
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


class TestFeedQueriesAndSwipeStatus:
    def _seed_feed_data(self, db_connection: sqlite3.Connection) -> None:
        insert_run_log(db_connection, _make_run_log())
        insert_post(db_connection, _make_post("post-1", platform="linkedin"))
        insert_post(db_connection, _make_post("post-2", platform="x"))
        insert_post(db_connection, _make_post("post-3", platform="reddit"))
        insert_post(db_connection, _make_post("post-4", platform="linkedin"))
        insert_classification(
            db_connection,
            _make_classification("cls-1", "post-1", "Read").model_copy(
                update={
                    "summary": "Summary 1",
                    "reasoning": "Reasoning 1",
                    "confidence": 0.81,
                    "classified_at": "2025-01-01T10:00:00+00:00",
                },
            ),
        )
        insert_classification(
            db_connection,
            _make_classification("cls-2", "post-2", "Read").model_copy(
                update={
                    "summary": "Summary 2",
                    "reasoning": "Reasoning 2",
                    "confidence": 0.95,
                    "classified_at": "2025-01-01T12:00:00+00:00",
                },
            ),
        )
        insert_classification(
            db_connection,
            _make_classification("cls-3", "post-3", "Skip").model_copy(
                update={"classified_at": "2025-01-01T11:00:00+00:00"},
            ),
        )
        insert_classification(
            db_connection,
            _make_classification("cls-4", "post-4", "Read").model_copy(
                update={"classified_at": "2025-01-01T09:00:00+00:00"},
            ),
        )
        db_connection.execute(
            "UPDATE classifications SET swipe_status = 'archived' WHERE id = ?",
            ("cls-4",),
        )
        db_connection.commit()

    def test_get_posts_for_feed_returns_joined_rows_ordered_by_classified_at(
        self,
        db_connection: sqlite3.Connection,
    ) -> None:
        self._seed_feed_data(db_connection)

        rows = get_posts_for_feed(
            db_connection,
            category="Read",
            swipe_status="pending",
            limit=20,
            offset=0,
        )

        assert [row["classification_id"] for row in rows] == ["cls-2", "cls-1"]
        expected_keys = {
            "id",
            "classification_id",
            "platform",
            "author_name",
            "author_url",
            "post_url",
            "post_text",
            "summary",
            "category",
            "confidence",
            "reasoning",
            "classified_at",
            "swipe_status",
            "note",
        }
        assert set(rows[0]) == expected_keys
        assert rows[0]["id"] == "post-2"
        assert rows[0]["platform"] == "x"
        assert rows[0]["summary"] == "Summary 2"
        assert rows[0]["swipe_status"] == "pending"
        assert rows[0]["note"] is None

        paged = get_posts_for_feed(
            db_connection,
            category="Read",
            swipe_status="pending",
            limit=1,
            offset=1,
        )
        assert len(paged) == 1
        assert paged[0]["classification_id"] == "cls-1"

    def test_get_posts_for_feed_empty_results(self, db_connection: sqlite3.Connection) -> None:
        assert get_posts_for_feed(db_connection) == []

    def test_count_posts_for_feed_respects_filters(self, db_connection: sqlite3.Connection) -> None:
        self._seed_feed_data(db_connection)

        assert count_posts_for_feed(db_connection, category="Read", swipe_status="pending") == 2
        assert count_posts_for_feed(db_connection, category="Read", swipe_status="archived") == 1
        assert count_posts_for_feed(db_connection, category="Skip", swipe_status="pending") == 1
        assert count_posts_for_feed(db_connection, category="Read", swipe_status="pending", platform="x") == 1
        assert count_posts_for_feed(db_connection, category="Read", swipe_status="pending", platform="linkedin") == 1

    def test_count_posts_for_feed_empty_results(self, db_connection: sqlite3.Connection) -> None:
        assert count_posts_for_feed(db_connection) == 0

    def test_get_posts_for_feed_filters_by_platform(self, db_connection: sqlite3.Connection) -> None:
        self._seed_feed_data(db_connection)

        rows = get_posts_for_feed(
            db_connection,
            category="Read",
            swipe_status="pending",
            platform="linkedin",
            limit=20,
            offset=0,
        )
        assert [row["classification_id"] for row in rows] == ["cls-1"]
        assert {row["platform"] for row in rows} == {"linkedin"}

    def test_get_posts_for_feed_includes_note_text_when_present(
        self,
        db_connection: sqlite3.Connection,
    ) -> None:
        self._seed_feed_data(db_connection)
        upsert_note(db_connection, "cls-1", "Track this topic for weekly sync")

        rows = get_posts_for_feed(
            db_connection,
            category="Read",
            swipe_status="pending",
            platform="linkedin",
            limit=20,
            offset=0,
        )

        assert len(rows) == 1
        assert rows[0]["classification_id"] == "cls-1"
        assert rows[0]["note"] == "Track this topic for weekly sync"

    def test_update_swipe_status_sets_swiped_at_timestamp(
        self,
        db_connection: sqlite3.Connection,
    ) -> None:
        _seed_basic(db_connection)

        update_swipe_status(db_connection, "cls-1", "deleted")

        row = db_connection.execute(
            "SELECT swipe_status, swiped_at FROM classifications WHERE id = ?",
            ("cls-1",),
        ).fetchone()
        assert row is not None
        assert row["swipe_status"] == "deleted"
        assert row["swiped_at"] is not None
        parsed = datetime.fromisoformat(row["swiped_at"])
        assert parsed.tzinfo is not None
        assert parsed.utcoffset() == timedelta(0)

    def test_update_swipe_status_rejects_invalid_status(
        self,
        db_connection: sqlite3.Connection,
    ) -> None:
        _seed_basic(db_connection)

        with pytest.raises(ValueError, match="Invalid swipe status"):
            update_swipe_status(db_connection, "cls-1", "bad")

    def test_update_swipe_status_nonexistent_classification_id_is_noop(
        self,
        db_connection: sqlite3.Connection,
    ) -> None:
        _seed_basic(db_connection)

        update_swipe_status(db_connection, "missing", "archived")

        row = db_connection.execute(
            "SELECT swipe_status, swiped_at FROM classifications WHERE id = ?",
            ("cls-1",),
        ).fetchone()
        assert row is not None
        assert row["swipe_status"] == "pending"
        assert row["swiped_at"] is None


class TestNotes:
    def test_upsert_note_inserts_new_note(self, db_connection: sqlite3.Connection) -> None:
        _seed_basic(db_connection)

        upsert_note(db_connection, "cls-1", "Useful idea for next sprint")
        note = get_note_by_classification_id(db_connection, "cls-1")

        assert note is not None
        assert note["classification_id"] == "cls-1"
        assert note["note_text"] == "Useful idea for next sprint"
        assert note["created_at"] is not None
        assert note["updated_at"] is not None

    def test_upsert_note_updates_existing_note_without_changing_created_at(
        self,
        db_connection: sqlite3.Connection,
    ) -> None:
        _seed_basic(db_connection)

        upsert_note(db_connection, "cls-1", "first")
        first = get_note_by_classification_id(db_connection, "cls-1")
        assert first is not None

        upsert_note(db_connection, "cls-1", "updated")
        second = get_note_by_classification_id(db_connection, "cls-1")

        assert second is not None
        assert second["note_text"] == "updated"
        assert second["created_at"] == first["created_at"]
        assert second["updated_at"] >= first["updated_at"]

    def test_delete_note_by_classification_id_removes_note(
        self,
        db_connection: sqlite3.Connection,
    ) -> None:
        _seed_basic(db_connection)
        upsert_note(db_connection, "cls-1", "delete me")

        delete_note_by_classification_id(db_connection, "cls-1")
        note = get_note_by_classification_id(db_connection, "cls-1")

        assert note is None


class TestFeedback:
    def test_record_feedback_for_classification_inserts_context_fields(
        self,
        db_connection: sqlite3.Connection,
    ) -> None:
        insert_run_log(db_connection, _make_run_log())
        insert_post(db_connection, _make_post(platform="x"))
        insert_classification(
            db_connection,
            _make_classification(category="Read", confidence=0.87),
        )

        saved = record_feedback_for_classification(db_connection, "cls-1", "archive")

        assert saved is not None
        assert saved["classification_id"] == "cls-1"
        assert saved["action"] == "archive"
        assert saved["platform"] == "x"
        assert saved["category"] == "Read"
        assert saved["confidence"] == 0.87
        assert saved["id"]
        parsed = datetime.fromisoformat(saved["created_at"])
        assert parsed.tzinfo is not None
        assert parsed.utcoffset() == timedelta(0)

    def test_record_feedback_for_classification_rejects_invalid_action(
        self,
        db_connection: sqlite3.Connection,
    ) -> None:
        _seed_basic(db_connection)

        with pytest.raises(ValueError, match="Invalid feedback action"):
            record_feedback_for_classification(db_connection, "cls-1", "maybe")

    def test_record_feedback_for_classification_returns_none_when_missing_classification(
        self,
        db_connection: sqlite3.Connection,
    ) -> None:
        _seed_basic(db_connection)

        saved = record_feedback_for_classification(db_connection, "missing", "archive")
        assert saved is None
        rows = db_connection.execute("SELECT * FROM feedback").fetchall()
        assert rows == []

    def test_get_feedback_stats_returns_platform_category_ratios_and_override_distribution(
        self,
        db_connection: sqlite3.Connection,
    ) -> None:
        insert_run_log(db_connection, _make_run_log())
        insert_post(db_connection, _make_post("post-1", platform="linkedin"))
        insert_post(db_connection, _make_post("post-2", platform="linkedin"))
        insert_post(db_connection, _make_post("post-3", platform="x"))
        insert_post(db_connection, _make_post("post-4", platform="x"))
        insert_classification(db_connection, _make_classification("cls-1", "post-1", "Read", confidence=0.95))
        insert_classification(db_connection, _make_classification("cls-2", "post-2", "Read", confidence=0.82))
        insert_classification(db_connection, _make_classification("cls-3", "post-3", "Skip", confidence=0.21))
        insert_classification(db_connection, _make_classification("cls-4", "post-4", "Skip", confidence=0.11))

        record_feedback_for_classification(db_connection, "cls-1", "archive")
        record_feedback_for_classification(db_connection, "cls-2", "delete")
        record_feedback_for_classification(db_connection, "cls-3", "archive")
        record_feedback_for_classification(db_connection, "cls-4", "delete")

        stats = get_feedback_stats(db_connection)
        assert stats["total_feedback"] == 4

        by_platform = {row["platform"]: row for row in stats["by_platform"]}
        assert by_platform["linkedin"] == {
            "platform": "linkedin",
            "archive_count": 1,
            "delete_count": 1,
            "total": 2,
            "archive_ratio": 0.5,
            "delete_ratio": 0.5,
        }
        assert by_platform["x"] == {
            "platform": "x",
            "archive_count": 1,
            "delete_count": 1,
            "total": 2,
            "archive_ratio": 0.5,
            "delete_ratio": 0.5,
        }

        by_category = {row["category"]: row for row in stats["by_category"]}
        assert by_category["Read"] == {
            "category": "Read",
            "archive_count": 1,
            "delete_count": 1,
            "total": 2,
            "archive_ratio": 0.5,
            "delete_ratio": 0.5,
        }
        assert by_category["Skip"] == {
            "category": "Skip",
            "archive_count": 1,
            "delete_count": 1,
            "total": 2,
            "archive_ratio": 0.5,
            "delete_ratio": 0.5,
        }

        overrides = stats["override_confidence"]
        assert overrides["total_overrides"] == 2
        assert overrides["average_confidence"] == pytest.approx(0.515)
        distribution = {row["bucket"]: row["count"] for row in overrides["distribution"]}
        assert distribution == {
            "0.0-0.2": 0,
            "0.2-0.4": 1,
            "0.4-0.6": 0,
            "0.6-0.8": 0,
            "0.8-1.0": 1,
        }


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
