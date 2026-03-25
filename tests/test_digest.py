from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from noise_cancel.config import AppConfig
from noise_cancel.logger.repository import insert_classification, insert_post
from noise_cancel.models import Classification, Post


def _insert_classified_post(
    conn,
    *,
    post_id: str,
    classification_id: str,
    platform: str,
    category: str,
    classified_at: str,
    post_text: str,
) -> None:
    insert_post(
        conn,
        Post(
            id=post_id,
            platform=platform,
            author_name=f"Author {post_id}",
            post_url=f"https://example.com/{post_id}",
            post_text=post_text,
            scraped_at=classified_at,
        ),
    )
    insert_classification(
        conn,
        Classification(
            id=classification_id,
            post_id=post_id,
            category=category,
            confidence=0.9,
            reasoning=f"Reasoning {classification_id}",
            summary=f"Summary {classification_id}",
            model_used="test-model",
            classified_at=classified_at,
        ),
    )


def test_generate_daily_digest_uses_recent_read_posts_and_structured_claude_response(
    db_connection,
    app_config: AppConfig,
    monkeypatch,
) -> None:
    from noise_cancel.digest.service import generate_daily_digest

    now = datetime(2026, 2, 26, 12, 0, tzinfo=timezone.utc)
    recent = (now - timedelta(hours=2)).isoformat()
    old = (now - timedelta(hours=30)).isoformat()
    skip_recent = (now - timedelta(hours=1)).isoformat()

    _insert_classified_post(
        db_connection,
        post_id="post-read-recent",
        classification_id="cls-read-recent",
        platform="linkedin",
        category="Read",
        classified_at=recent,
        post_text="Recent read post about AI infrastructure trends.",
    )
    _insert_classified_post(
        db_connection,
        post_id="post-read-old",
        classification_id="cls-read-old",
        platform="x",
        category="Read",
        classified_at=old,
        post_text="Old read post that should be excluded from the 24h window.",
    )
    _insert_classified_post(
        db_connection,
        post_id="post-skip-recent",
        classification_id="cls-skip-recent",
        platform="reddit",
        category="Skip",
        classified_at=skip_recent,
        post_text="Recent skip post that should not be sent to Claude for digest themes.",
    )

    class FakeAnthropicClient:
        def __init__(self) -> None:
            self.calls: list[dict] = []
            self.messages = SimpleNamespace(create=self._create)

        def _create(self, **kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(
                content=[
                    SimpleNamespace(
                        type="tool_use",
                        input={
                            "themes": [
                                "AI infrastructure is becoming more operational and cost-aware.",
                                "Cross-platform discussions are converging on deployment reliability.",
                                "Teams are prioritizing measurable production outcomes over hype.",
                            ],
                            "notable_posts": [
                                "LinkedIn: practical guide to reducing inference spend with batching.",
                                "Reddit: migration checklist for serving model updates safely.",
                            ],
                        },
                    )
                ]
            )

    fake_client = FakeAnthropicClient()
    monkeypatch.setattr(
        "noise_cancel.digest.service.import_module",
        lambda _: SimpleNamespace(Anthropic=lambda: fake_client),
    )

    digest_text = generate_daily_digest(
        db_connection,
        app_config,
        now=now,
    )

    assert len(fake_client.calls) == 1
    user_prompt = fake_client.calls[0]["messages"][0]["content"]
    assert "Recent read post about AI infrastructure trends." in user_prompt
    assert "Old read post that should be excluded" not in user_prompt
    assert "Recent skip post that should not be sent" not in user_prompt

    assert "Daily Feed Digest" in digest_text
    assert "Date: 2026-02-26" in digest_text
    assert "Platform breakdown" in digest_text
    assert "- linkedin: 1" in digest_text
    assert "Theme summary" in digest_text
    assert "Notable posts" in digest_text
    assert "Total stats" in digest_text
    assert "saved: 1" in digest_text
    assert "filtered: 1" in digest_text


def test_generate_daily_digest_skips_claude_when_no_recent_read_posts(
    db_connection,
    app_config: AppConfig,
    monkeypatch,
) -> None:
    from noise_cancel.digest.service import generate_daily_digest

    now = datetime(2026, 2, 26, 12, 0, tzinfo=timezone.utc)
    recent = (now - timedelta(hours=2)).isoformat()
    _insert_classified_post(
        db_connection,
        post_id="post-skip-recent",
        classification_id="cls-skip-recent",
        platform="reddit",
        category="Skip",
        classified_at=recent,
        post_text="Only skip content in the time window.",
    )

    called = False

    def _fail_if_called(_: str):
        nonlocal called
        called = True
        raise AssertionError

    monkeypatch.setattr("noise_cancel.digest.service.import_module", _fail_if_called)

    digest_text = generate_daily_digest(
        db_connection,
        app_config,
        now=now,
    )

    assert called is False
    assert "No Read posts found in the last 24 hours." in digest_text
    assert "saved: 0" in digest_text
    assert "filtered: 1" in digest_text


def test_generate_and_deliver_digest_uses_plugin_delivery_when_enabled(
    db_connection,
    app_config: AppConfig,
    monkeypatch,
) -> None:
    from noise_cancel.digest.service import generate_and_deliver_digest

    monkeypatch.setattr(
        "noise_cancel.digest.service.generate_daily_digest",
        lambda conn, config, now=None: "Daily Feed Digest\n\nmock digest body",
    )

    delivered: list[tuple[str, str]] = []

    class FakePlugin:
        def validate_config(self, config: dict[str, object]) -> None:
            assert config["type"] == "slack"

        def deliver_digest(self, digest_text: str, config: AppConfig, plugin_config: dict[str, object]) -> bool:
            delivered.append((digest_text, plugin_config["type"]))  # type: ignore[index]
            return True

    monkeypatch.setattr("noise_cancel.digest.service.get_delivery_plugin_class", lambda _: FakePlugin)

    result = generate_and_deliver_digest(db_connection, app_config)

    assert result.digest_text.startswith("Daily Feed Digest")
    assert result.delivery_enabled is True
    assert result.delivered_plugins == 1
    assert delivered == [("Daily Feed Digest\n\nmock digest body", "slack")]
