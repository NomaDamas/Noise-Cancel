from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import httpx

from noise_cancel.config import AppConfig
from noise_cancel.delivery.blocks import build_post_blocks
from noise_cancel.delivery.slack import deliver_posts, send_to_slack
from noise_cancel.models import Classification, Post

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_post(
    post_id: str = "post-1",
    author_name: str = "Jane Doe",
    author_url: str | None = "https://linkedin.com/in/janedoe",
    post_url: str | None = "https://linkedin.com/posts/janedoe-123",
    post_text: str = "This is an insightful post about machine learning and AI trends in 2025.",
) -> Post:
    return Post(id=post_id, author_name=author_name, author_url=author_url, post_url=post_url, post_text=post_text)


def _make_classification(
    cls_id: str = "cls-1",
    post_id: str = "post-1",
    category: str = "Read",
    confidence: float = 0.92,
    reasoning: str = "Highly relevant ML content.",
    summary: str = "A post about ML and AI trends. Covers recent advances and predictions for the future.",
    model_used: str = "claude-sonnet-4-6",
) -> Classification:
    return Classification(
        id=cls_id,
        post_id=post_id,
        category=category,
        confidence=confidence,
        reasoning=reasoning,
        summary=summary,
        model_used=model_used,
    )


def _slack_config(**overrides) -> dict:
    defaults = {
        "include_categories": ["Read"],
    }
    defaults.update(overrides)
    return defaults


# ===========================================================================
# Tests for blocks.py
# ===========================================================================


class TestBuildPostBlocks:
    def test_basic_block_structure(self):
        post = _make_post()
        cls = _make_classification()
        blocks = build_post_blocks(post, cls)

        assert isinstance(blocks, list)
        assert all(isinstance(b, dict) for b in blocks)

        block_types = [b["type"] for b in blocks]
        assert "section" in block_types
        assert "actions" in block_types
        # No header or context blocks in new layout
        assert "header" not in block_types
        assert "context" not in block_types

    def test_author_name_displayed_without_link(self):
        post = _make_post(author_url="https://linkedin.com/in/janedoe")
        cls = _make_classification()
        blocks = build_post_blocks(post, cls)

        sections = [b for b in blocks if b["type"] == "section"]
        author_section = sections[0]
        text_content = author_section["text"]["text"]
        assert text_content == "*Jane Doe*"
        assert "<" not in text_content  # no Slack link syntax

    def test_author_plain_when_no_url(self):
        post = _make_post(author_url=None)
        cls = _make_classification()
        blocks = build_post_blocks(post, cls)

        sections = [b for b in blocks if b["type"] == "section"]
        author_section = sections[0]
        text_content = author_section["text"]["text"]
        assert "Jane Doe" in text_content
        assert "<" not in text_content

    def test_summary_displayed(self):
        post = _make_post()
        cls = _make_classification(summary="This is a 3-line summary. It covers key points. Very informative.")
        blocks = build_post_blocks(post, cls)

        sections = [b for b in blocks if b["type"] == "section"]
        summary_section = sections[1]
        assert "This is a 3-line summary" in summary_section["text"]["text"]

    def test_falls_back_to_post_text_when_no_summary(self):
        post = _make_post(post_text="Original post text here")
        cls = _make_classification(summary="")
        blocks = build_post_blocks(post, cls)

        sections = [b for b in blocks if b["type"] == "section"]
        summary_section = sections[1]
        assert "Original post text here" in summary_section["text"]["text"]

    def test_fallback_text_truncated_at_300(self):
        long_text = "A" * 500
        post = _make_post(post_text=long_text)
        cls = _make_classification(summary="")
        blocks = build_post_blocks(post, cls)

        sections = [b for b in blocks if b["type"] == "section"]
        summary_section = sections[1]
        assert len(summary_section["text"]["text"]) == 300

    def test_linkedin_link_button_when_post_url_exists(self):
        post = _make_post(post_url="https://linkedin.com/posts/123")
        cls = _make_classification()
        blocks = build_post_blocks(post, cls)

        actions = [b for b in blocks if b["type"] == "actions"]
        assert len(actions) == 1
        link_buttons = [e for e in actions[0]["elements"] if e.get("url")]
        assert len(link_buttons) >= 1
        assert link_buttons[0]["url"] == "https://linkedin.com/posts/123"

    def test_no_linkedin_link_when_no_post_url(self):
        post = _make_post(post_url=None)
        cls = _make_classification()
        blocks = build_post_blocks(post, cls)

        actions = [b for b in blocks if b["type"] == "actions"]
        assert len(actions) == 0


# ===========================================================================
# Tests for slack.py
# ===========================================================================


class TestSendToSlack:
    def test_send_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "ok"

        with patch("noise_cancel.delivery.slack.httpx.post", return_value=mock_response) as mock_post:
            result = send_to_slack("https://hooks.slack.com/test", [{"type": "section"}], text="fallback")

        assert result is True
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert call_kwargs[0][0] == "https://hooks.slack.com/test"

    def test_send_failure_status(self):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "server_error"

        with patch("noise_cancel.delivery.slack.httpx.post", return_value=mock_response):
            result = send_to_slack("https://hooks.slack.com/test", [{"type": "section"}])

        assert result is False

    def test_send_failure_exception(self):
        with patch("noise_cancel.delivery.slack.httpx.post", side_effect=httpx.HTTPError("connection failed")):
            result = send_to_slack("https://hooks.slack.com/test", [{"type": "section"}])

        assert result is False


class TestDeliverPosts:
    def test_delivers_matching_categories(self):
        post_must = _make_post(post_id="p1")
        cls_must = _make_classification(post_id="p1", category="Read")

        post_noise = _make_post(post_id="p2")
        cls_noise = _make_classification(post_id="p2", category="Skip")

        config = AppConfig(
            delivery={
                "method": "slack",
                "slack": _slack_config(include_categories=["Read"]),
            }
        )

        with (
            patch.dict(os.environ, {"SLACK_WEBHOOK_URL": "https://hooks.slack.com/test"}),
            patch("noise_cancel.delivery.slack.send_to_slack", return_value=True) as mock_send,
        ):
            count = deliver_posts(
                [(post_must, cls_must), (post_noise, cls_noise)],
                config,
            )

        assert count == 1
        mock_send.assert_called_once()

    def test_returns_zero_when_no_webhook_url(self):
        post = _make_post()
        cls = _make_classification()
        config = AppConfig(
            delivery={
                "method": "slack",
                "slack": _slack_config(),
            }
        )

        with patch.dict(os.environ, {}, clear=True):
            # Remove SLACK_WEBHOOK_URL if it exists
            env = os.environ.copy()
            env.pop("SLACK_WEBHOOK_URL", None)
            with patch.dict(os.environ, env, clear=True):
                count = deliver_posts([(post, cls)], config)

        assert count == 0

    def test_counts_successful_deliveries(self):
        posts_cls = [
            (_make_post(post_id=f"p{i}"), _make_classification(post_id=f"p{i}", category="Read")) for i in range(3)
        ]
        config = AppConfig(
            delivery={
                "method": "slack",
                "slack": _slack_config(include_categories=["Read"]),
            }
        )

        # First two succeed, third fails
        with (
            patch.dict(os.environ, {"SLACK_WEBHOOK_URL": "https://hooks.slack.com/test"}),
            patch("noise_cancel.delivery.slack.send_to_slack", side_effect=[True, True, False]),
        ):
            count = deliver_posts(posts_cls, config)

        assert count == 2
