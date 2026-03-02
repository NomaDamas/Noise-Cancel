from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from noise_cancel.classifier.schemas import PostClassification
from noise_cancel.config import AppConfig
from noise_cancel.dedup.semantic import VerificationResult
from noise_cancel.logger.repository import insert_run_log
from noise_cancel.models import Post, RunLog
from server.main import create_app


def _test_config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        general={"data_dir": str(tmp_path / "data"), "max_posts_per_run": 50, "language": "english"},
        scraper={"headless": True, "scroll_count": 1},
        classifier={
            "model": "claude-sonnet-4-6",
            "batch_size": 10,
            "temperature": 0.0,
            "categories": [],
            "whitelist": {"keywords": [], "authors": []},
            "blacklist": {"keywords": [], "authors": []},
        },
        delivery={"method": "slack", "slack": {"include_categories": ["Read"]}},
    )


def _build_client(
    tmp_path: Path, monkeypatch, config: AppConfig | None = None
) -> tuple[TestClient, sqlite3.Connection]:
    test_config = config or _test_config(tmp_path)
    monkeypatch.setattr("server.main.load_config", lambda: test_config)
    # Use a file-based DB so the pipeline service (which creates its own
    # connection via _resolve_db_path) shares the same database as the
    # lifespan-managed connection that the router uses.
    db_path = Path(test_config.general["data_dir"]) / "noise_cancel.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    client = TestClient(create_app())
    # Open a read connection to the same file for test assertions.
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return client, conn


_SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/test"
_SESSION_EXPIRED_ERROR = "Session expired. Run login to refresh."


class FakeSessionExpiredError(RuntimeError):
    def __init__(self) -> None:
        super().__init__(_SESSION_EXPIRED_ERROR)


def _session_test_config(tmp_path: Path, *, delivery: dict[str, object]) -> AppConfig:
    return AppConfig(
        general={"data_dir": str(tmp_path / "data"), "max_posts_per_run": 50, "language": "english"},
        scraper={
            "platforms": {
                "x": {"enabled": True, "scroll_count": 1, "session_warning_days": 1},
            }
        },
        classifier={
            "model": "claude-sonnet-4-6",
            "batch_size": 10,
            "temperature": 0.0,
            "categories": [],
            "whitelist": {"keywords": [], "authors": []},
            "blacklist": {"keywords": [], "authors": []},
        },
        delivery=delivery,
    )


def _install_fake_x_registry(monkeypatch, scraper_class: type[object]) -> None:
    class FakeRegistry:
        def get(self, platform: str):
            return {"x": scraper_class}[platform]

    class FakeClassifier:
        def __init__(self, _config: AppConfig) -> None:
            pass

        def classify_posts(self, posts: list[Post]) -> list[PostClassification]:
            assert posts == []
            return []

    monkeypatch.setattr("server.services.pipeline.SCRAPER_REGISTRY", FakeRegistry())
    monkeypatch.setattr("server.services.pipeline.ClassificationEngine", FakeClassifier)


def _install_fake_x_session_pipeline(monkeypatch, *, expires_in_days: float) -> None:
    class FakeXScraper:
        def __init__(self, _config: AppConfig) -> None:
            pass

        def session_age_days(self) -> float | None:
            return expires_in_days

        def session_expires_in_days(self) -> float | None:
            return expires_in_days

        async def scrape_feed(self, scroll_count: int = 10) -> list[Post]:
            assert scroll_count == 1
            return []

        async def close(self) -> None:
            return None

    _install_fake_x_registry(monkeypatch, FakeXScraper)


def _install_fake_x_session_pipeline_error(
    monkeypatch,
    *,
    expires_in_days: float,
    scrape_error: RuntimeError,
) -> None:
    class FakeXScraper:
        def __init__(self, _config: AppConfig) -> None:
            pass

        def session_age_days(self) -> float | None:
            return expires_in_days

        def session_expires_in_days(self) -> float | None:
            return expires_in_days

        async def scrape_feed(self, scroll_count: int = 10) -> list[Post]:
            assert scroll_count == 1
            raise scrape_error

        async def close(self) -> None:
            return None

    _install_fake_x_registry(monkeypatch, FakeXScraper)


def _install_fake_slack_sender(monkeypatch, sent_messages: list[str]) -> None:

    def _fake_send_to_slack(webhook_url: str, blocks: list[dict], text: str = "") -> bool:
        assert webhook_url == _SLACK_WEBHOOK_URL
        sent_messages.append(text)
        return True

    monkeypatch.setattr("noise_cancel.delivery.slack.send_to_slack", _fake_send_to_slack)


def test_run_pipeline_creates_run_log_and_returns_accepted(tmp_path: Path, monkeypatch) -> None:
    class FakeScraper:
        def __init__(self, _config: AppConfig) -> None:
            pass

        async def scrape_feed(self, scroll_count: int = 10) -> list[Post]:
            assert scroll_count == 1
            return [
                Post(
                    id="post-1",
                    author_name="Author One",
                    author_url="https://linkedin.com/in/one",
                    post_url="https://linkedin.com/posts/one",
                    post_text="First post",
                ),
                Post(
                    id="post-2",
                    author_name="Author Two",
                    author_url="https://linkedin.com/in/two",
                    post_url="https://linkedin.com/posts/two",
                    post_text="Second post",
                ),
            ]

    class FakeClassifier:
        def __init__(self, _config: AppConfig) -> None:
            pass

        def classify_posts(self, posts: list[Post]) -> list[PostClassification]:
            assert [post.id for post in posts] == ["post-1"]
            return [
                PostClassification(
                    post_index=0,
                    category="Read",
                    confidence=0.96,
                    reasoning="Useful",
                    summary="Keep this one",
                    applied_rules=[],
                )
            ]

    class FakeRegistry:
        def get(self, platform: str):
            if platform == "linkedin":
                return FakeScraper
            raise KeyError(platform)

    monkeypatch.setattr("server.services.pipeline.SCRAPER_REGISTRY", FakeRegistry())
    monkeypatch.setattr("server.services.pipeline.ClassificationEngine", FakeClassifier)

    client, conn = _build_client(tmp_path, monkeypatch)
    with client:
        response = client.post(
            "/api/pipeline/run",
            json={"limit": 1, "skip_scrape": False},
        )

        assert response.status_code == 202
        payload = response.json()
        assert set(payload) == {"run_id", "status", "message"}
        assert payload["status"] == "accepted"

        run_log = conn.execute(
            "SELECT run_type, status, posts_scraped, posts_classified FROM run_logs WHERE id = ?",
            (payload["run_id"],),
        ).fetchone()
        assert run_log is not None
        assert run_log["run_type"] == "pipeline"
        assert run_log["status"] == "completed"
        assert run_log["posts_scraped"] == 1
        assert run_log["posts_classified"] == 1


def test_run_pipeline_allows_empty_body(tmp_path: Path, monkeypatch) -> None:
    class FakeScraper:
        def __init__(self, _config: AppConfig) -> None:
            pass

        async def scrape_feed(self, scroll_count: int = 10) -> list[Post]:
            assert scroll_count == 1
            return []

    class FakeClassifier:
        def __init__(self, _config: AppConfig) -> None:
            pass

        def classify_posts(self, posts: list[Post]) -> list[PostClassification]:
            assert posts == []
            return []

    class FakeRegistry:
        def get(self, platform: str):
            if platform == "linkedin":
                return FakeScraper
            raise KeyError(platform)

    monkeypatch.setattr("server.services.pipeline.SCRAPER_REGISTRY", FakeRegistry())
    monkeypatch.setattr("server.services.pipeline.ClassificationEngine", FakeClassifier)

    client, conn = _build_client(tmp_path, monkeypatch)
    with client:
        response = client.post("/api/pipeline/run")

        assert response.status_code == 202
        payload = response.json()
        run_log = conn.execute("SELECT id, run_type FROM run_logs WHERE id = ?", (payload["run_id"],)).fetchone()
        assert run_log is not None
        assert run_log["run_type"] == "pipeline"


def test_run_pipeline_scrapes_all_enabled_platforms(tmp_path: Path, monkeypatch) -> None:
    config = AppConfig(
        general={"data_dir": str(tmp_path / "data"), "max_posts_per_run": 50, "language": "english"},
        scraper={
            "platforms": {
                "linkedin": {"enabled": True, "scroll_count": 1},
                "x": {"enabled": True, "scroll_count": 2},
                "threads": {"enabled": False, "scroll_count": 3},
            }
        },
        classifier={
            "model": "claude-sonnet-4-6",
            "batch_size": 10,
            "temperature": 0.0,
            "categories": [],
            "whitelist": {"keywords": [], "authors": []},
            "blacklist": {"keywords": [], "authors": []},
        },
        delivery={"method": "slack", "slack": {"include_categories": ["Read"]}},
    )

    class FakeLinkedInScraper:
        def __init__(self, _config: AppConfig) -> None:
            pass

        async def scrape_feed(self, scroll_count: int = 10) -> list[Post]:
            assert scroll_count == 1
            return [Post(id="li-1", author_name="Alice", post_text="LinkedIn post")]

    class FakeXScraper:
        def __init__(self, _config: AppConfig) -> None:
            pass

        async def scrape_feed(self, scroll_count: int = 10) -> list[Post]:
            assert scroll_count == 2
            return [Post(id="x-1", author_name="Bob", post_text="X post")]

    class FakeRegistry:
        def get(self, platform: str):
            if platform == "linkedin":
                return FakeLinkedInScraper
            if platform == "x":
                return FakeXScraper
            raise KeyError(platform)

    class FakeClassifier:
        def __init__(self, _config: AppConfig) -> None:
            pass

        def classify_posts(self, posts: list[Post]) -> list[PostClassification]:
            assert {(post.id, post.platform) for post in posts} == {
                ("li-1", "linkedin"),
                ("x-1", "x"),
            }
            return [
                PostClassification(
                    post_index=0,
                    category="Read",
                    confidence=0.9,
                    reasoning="useful",
                    summary="summary 1",
                    applied_rules=[],
                ),
                PostClassification(
                    post_index=1,
                    category="Read",
                    confidence=0.8,
                    reasoning="useful",
                    summary="summary 2",
                    applied_rules=[],
                ),
            ]

    monkeypatch.setattr("server.services.pipeline.SCRAPER_REGISTRY", FakeRegistry())
    monkeypatch.setattr("server.services.pipeline.ClassificationEngine", FakeClassifier)

    client, conn = _build_client(tmp_path, monkeypatch, config=config)
    with client:
        response = client.post("/api/pipeline/run", json={"limit": 10, "skip_scrape": False})

        assert response.status_code == 202
        payload = response.json()

        run_log = conn.execute(
            "SELECT status, posts_scraped, posts_classified FROM run_logs WHERE id = ?",
            (payload["run_id"],),
        ).fetchone()
        assert run_log is not None
        assert run_log["status"] == "completed"
        assert run_log["posts_scraped"] == 2
        assert run_log["posts_classified"] == 2

        posts = conn.execute("SELECT id, platform FROM posts ORDER BY id").fetchall()
        assert [(row["id"], row["platform"]) for row in posts] == [("li-1", "linkedin"), ("x-1", "x")]


def test_run_pipeline_applies_semantic_dedup_before_classification(tmp_path: Path, monkeypatch) -> None:  # noqa: C901
    config = AppConfig(
        general={"data_dir": str(tmp_path / "data"), "max_posts_per_run": 50, "language": "english"},
        scraper={
            "platforms": {
                "linkedin": {"enabled": True, "scroll_count": 1},
                "x": {"enabled": True, "scroll_count": 1},
            }
        },
        classifier={
            "model": "claude-sonnet-4-6",
            "batch_size": 10,
            "temperature": 0.0,
            "categories": [],
            "whitelist": {"keywords": [], "authors": []},
            "blacklist": {"keywords": [], "authors": []},
        },
        dedup={
            "semantic": {
                "enabled": True,
                "provider": "sentence-transformers",
                "model": "all-MiniLM-L6-v2",
                "threshold": 0.85,
            }
        },
        delivery={"method": "slack", "slack": {"include_categories": ["Read"]}},
    )

    class FakeLinkedInScraper:
        def __init__(self, _config: AppConfig) -> None:
            pass

        async def scrape_feed(self, scroll_count: int = 10) -> list[Post]:
            assert scroll_count == 1
            return [
                Post(
                    id="li-1",
                    platform="linkedin",
                    author_name="Alice",
                    post_text="AI startup raises funding round",
                    post_url="https://example.com/li-1",
                )
            ]

    class FakeXScraper:
        def __init__(self, _config: AppConfig) -> None:
            pass

        async def scrape_feed(self, scroll_count: int = 10) -> list[Post]:
            assert scroll_count == 1
            return [
                Post(
                    id="x-1",
                    platform="x",
                    author_name="Bob",
                    post_text="AI startup raises funding round today",
                    post_url="https://example.com/x-1",
                )
            ]

    class FakeRegistry:
        def get(self, platform: str):
            if platform == "linkedin":
                return FakeLinkedInScraper
            if platform == "x":
                return FakeXScraper
            raise KeyError(platform)

    class FakeEmbedder:
        model = "unit-test-embedder"

        def embed(self, texts: list[str]) -> list[list[float]]:
            vectors: list[list[float]] = []
            for text in texts:
                if text.startswith("AI startup raises funding round"):
                    vectors.append([1.0, 0.0])
                else:
                    vectors.append([0.0, 1.0])
            return vectors

    class FakeVerifier:
        def __init__(self, _config: AppConfig) -> None:
            pass

        def verify(self, source_text: str, candidate_text: str) -> VerificationResult:
            if source_text.startswith("AI startup raises funding round") and candidate_text.startswith(
                "AI startup raises funding round"
            ):
                return VerificationResult(is_duplicate=True, reasoning="same post re-shared")
            return VerificationResult(is_duplicate=False, reasoning="different content")

    class FakeClassifier:
        def __init__(self, _config: AppConfig) -> None:
            pass

        def classify_posts(self, posts: list[Post]) -> list[PostClassification]:
            assert [(post.id, post.platform) for post in posts] == [("li-1", "linkedin")]
            return [
                PostClassification(
                    post_index=0,
                    category="Read",
                    confidence=0.9,
                    reasoning="useful",
                    summary="summary",
                    applied_rules=[],
                )
            ]

    monkeypatch.setattr("server.services.pipeline.SCRAPER_REGISTRY", FakeRegistry())
    monkeypatch.setattr("server.services.pipeline.ClassificationEngine", FakeClassifier)
    monkeypatch.setattr("server.services.pipeline.create_embedder_from_config", lambda _config: FakeEmbedder())
    monkeypatch.setattr("server.services.pipeline.ClaudeDuplicateVerifier", FakeVerifier)

    client, conn = _build_client(tmp_path, monkeypatch, config=config)
    with client:
        response = client.post("/api/pipeline/run", json={"limit": 10, "skip_scrape": False})

        assert response.status_code == 202
        payload = response.json()

        run_log = conn.execute(
            "SELECT status, posts_scraped, posts_classified FROM run_logs WHERE id = ?",
            (payload["run_id"],),
        ).fetchone()
        assert run_log is not None
        assert run_log["status"] == "completed"
        assert run_log["posts_scraped"] == 2
        assert run_log["posts_classified"] == 1

        duplicate_row = conn.execute(
            "SELECT category, swipe_status FROM classifications WHERE post_id = ?",
            ("x-1",),
        ).fetchone()
        assert duplicate_row is not None
        assert duplicate_row["category"] == "Duplicate"
        assert duplicate_row["swipe_status"] == "duplicate"


def test_get_pipeline_status_returns_latest_run(tmp_path: Path, monkeypatch) -> None:
    client, conn = _build_client(tmp_path, monkeypatch)
    with client:
        insert_run_log(
            conn,
            RunLog(
                id="run-old",
                run_type="pipeline",
                started_at="2026-02-24T01:00:00+00:00",
                status="completed",
                posts_scraped=2,
                posts_classified=2,
                posts_delivered=0,
            ),
        )
        insert_run_log(
            conn,
            RunLog(
                id="run-new",
                run_type="pipeline",
                started_at="2026-02-25T01:00:00+00:00",
                status="running",
                posts_scraped=1,
                posts_classified=0,
                posts_delivered=0,
            ),
        )

        response = client.get("/api/pipeline/status")
        assert response.status_code == 200
        payload = response.json()
        assert payload["run_id"] == "run-new"
        assert payload["run_type"] == "pipeline"
        assert payload["status"] == "running"
        assert payload["posts_scraped"] == 1
        assert payload["posts_classified"] == 0


def test_run_pipeline_sends_session_warning_for_expiring_playwright_session(tmp_path: Path, monkeypatch) -> None:
    config = _session_test_config(
        tmp_path,
        delivery={"plugins": [{"type": "slack", "webhook_url": _SLACK_WEBHOOK_URL}]},
    )
    sent_messages: list[str] = []
    _install_fake_x_session_pipeline(monkeypatch, expires_in_days=6 / 24)
    _install_fake_slack_sender(monkeypatch, sent_messages)

    client, conn = _build_client(tmp_path, monkeypatch, config=config)
    with client:
        response = client.post("/api/pipeline/run", json={"limit": 10, "skip_scrape": False})

        assert response.status_code == 202
        run_id = response.json()["run_id"]
        run_log = conn.execute("SELECT status FROM run_logs WHERE id = ?", (run_id,)).fetchone()
        assert run_log is not None
        assert run_log["status"] == "completed"

    assert sent_messages == ["⚠️ X session expires in ~6h. Run `noise-cancel login --platform x` to refresh."]


def test_run_pipeline_sends_expired_alert_before_raising(tmp_path: Path, monkeypatch) -> None:
    config = _session_test_config(
        tmp_path,
        delivery={"plugins": [{"type": "slack", "webhook_url": _SLACK_WEBHOOK_URL}]},
    )
    sent_messages: list[str] = []
    _install_fake_x_session_pipeline_error(
        monkeypatch,
        expires_in_days=2.0,
        scrape_error=FakeSessionExpiredError(),
    )
    _install_fake_slack_sender(monkeypatch, sent_messages)

    client, conn = _build_client(tmp_path, monkeypatch, config=config)
    with client:
        response = client.post("/api/pipeline/run", json={"limit": 10, "skip_scrape": False})

        assert response.status_code == 202
        run_id = response.json()["run_id"]
        run_log = conn.execute("SELECT status, error_message FROM run_logs WHERE id = ?", (run_id,)).fetchone()
        assert run_log is not None
        # Single-platform failure no longer aborts the pipeline;
        # the run completes with a warning logged instead of erroring out.
        assert run_log["status"] == "completed"

    assert sent_messages == ["❌ X session expired."]


def test_run_pipeline_uses_stderr_fallback_when_no_delivery_plugins(tmp_path: Path, monkeypatch, capsys) -> None:
    config = _session_test_config(tmp_path, delivery={"method": "", "plugins": []})
    _install_fake_x_session_pipeline(monkeypatch, expires_in_days=12 / 24)

    client, _ = _build_client(tmp_path, monkeypatch, config=config)
    with client:
        response = client.post("/api/pipeline/run", json={"limit": 10, "skip_scrape": False})
        assert response.status_code == 202

    captured = capsys.readouterr()
    assert "⚠️ X session expires in ~12h. Run `noise-cancel login --platform x` to refresh." in captured.err
