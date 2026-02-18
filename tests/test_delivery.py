from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import httpx

from noise_cancel.config import AppConfig
from noise_cancel.delivery.blocks import build_post_blocks
from noise_cancel.delivery.feedback import (
    generate_mute_rule,
    parse_feedback_action,
    should_auto_generate_rule,
)
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
    model_used: str = "claude-sonnet-4-6",
) -> Classification:
    return Classification(
        id=cls_id, post_id=post_id, category=category, confidence=confidence, reasoning=reasoning, model_used=model_used
    )


def _slack_config(**overrides) -> dict:
    defaults = {
        "include_categories": ["Read"],
        "include_reasoning": True,
        "max_text_preview": 300,
        "enable_feedback_buttons": True,
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
        config = _slack_config()
        blocks = build_post_blocks(post, cls, config)

        # Should be a list of dicts
        assert isinstance(blocks, list)
        assert all(isinstance(b, dict) for b in blocks)

        # Check block types present
        block_types = [b["type"] for b in blocks]
        assert "header" in block_types
        assert "section" in block_types
        assert "context" in block_types
        assert "actions" in block_types

    def test_header_contains_category(self):
        post = _make_post()
        cls = _make_classification(category="Read")
        config = _slack_config()
        blocks = build_post_blocks(post, cls, config)

        header = next(b for b in blocks if b["type"] == "header")
        assert "Read" in header["text"]["text"]

    def test_author_linked_when_url_exists(self):
        post = _make_post(author_url="https://linkedin.com/in/janedoe")
        cls = _make_classification()
        config = _slack_config()
        blocks = build_post_blocks(post, cls, config)

        sections = [b for b in blocks if b["type"] == "section"]
        # First section should have author info with link
        author_section = sections[0]
        text_content = author_section["text"]["text"]
        assert "<https://linkedin.com/in/janedoe|Jane Doe>" in text_content

    def test_author_plain_when_no_url(self):
        post = _make_post(author_url=None)
        cls = _make_classification()
        config = _slack_config()
        blocks = build_post_blocks(post, cls, config)

        sections = [b for b in blocks if b["type"] == "section"]
        author_section = sections[0]
        text_content = author_section["text"]["text"]
        assert "Jane Doe" in text_content
        assert "<" not in text_content  # no Slack link syntax

    def test_text_truncation(self):
        long_text = "A" * 500
        post = _make_post(post_text=long_text)
        cls = _make_classification()
        config = _slack_config(max_text_preview=100)
        blocks = build_post_blocks(post, cls, config)

        sections = [b for b in blocks if b["type"] == "section"]
        # The preview section (second section) should be truncated
        preview_section = sections[1]
        preview_text = preview_section["text"]["text"]
        assert len(preview_text) <= 110  # 100 + ellipsis + minor overhead
        assert "..." in preview_text

    def test_text_not_truncated_when_short(self):
        post = _make_post(post_text="Short post")
        cls = _make_classification()
        config = _slack_config(max_text_preview=300)
        blocks = build_post_blocks(post, cls, config)

        sections = [b for b in blocks if b["type"] == "section"]
        preview_section = sections[1]
        assert "Short post" in preview_section["text"]["text"]
        assert "..." not in preview_section["text"]["text"]

    def test_reasoning_included_when_enabled(self):
        post = _make_post()
        cls = _make_classification(reasoning="Highly relevant ML content.")
        config = _slack_config(include_reasoning=True)
        blocks = build_post_blocks(post, cls, config)

        context_blocks = [b for b in blocks if b["type"] == "context"]
        assert len(context_blocks) >= 1
        context_text = str(context_blocks[0]["elements"])
        assert "Highly relevant ML content." in context_text

    def test_reasoning_excluded_when_disabled(self):
        post = _make_post()
        cls = _make_classification(reasoning="Highly relevant ML content.")
        config = _slack_config(include_reasoning=False)
        blocks = build_post_blocks(post, cls, config)

        context_blocks = [b for b in blocks if b["type"] == "context"]
        # Context block should exist (confidence), but not contain reasoning
        all_text = str(context_blocks)
        assert "Highly relevant ML content." not in all_text

    def test_confidence_in_context(self):
        post = _make_post()
        cls = _make_classification(confidence=0.92)
        config = _slack_config()
        blocks = build_post_blocks(post, cls, config)

        context_blocks = [b for b in blocks if b["type"] == "context"]
        context_text = str(context_blocks[0]["elements"])
        assert "92" in context_text  # 0.92 -> 92%

    def test_action_buttons_present(self):
        post = _make_post(post_id="post-42")
        cls = _make_classification()
        config = _slack_config(enable_feedback_buttons=True)
        blocks = build_post_blocks(post, cls, config)

        actions = [b for b in blocks if b["type"] == "actions"]
        assert len(actions) == 1
        buttons = actions[0]["elements"]
        values = [btn["value"] for btn in buttons if btn["type"] == "button" and "value" in btn]
        assert "useful|post-42" in values
        assert "not_useful|post-42" in values
        assert "mute_similar|post-42" in values

    def test_action_buttons_excluded_when_disabled(self):
        post = _make_post()
        cls = _make_classification()
        config = _slack_config(enable_feedback_buttons=False)
        blocks = build_post_blocks(post, cls, config)

        actions = [b for b in blocks if b["type"] == "actions"]
        # No actions block, or no feedback buttons
        if actions:
            buttons = [
                e
                for e in actions[0]["elements"]
                if e.get("value", "").startswith(("useful", "not_useful", "mute_similar"))
            ]
            assert len(buttons) == 0

    def test_linkedin_link_button_when_post_url_exists(self):
        post = _make_post(post_url="https://linkedin.com/posts/123")
        cls = _make_classification()
        config = _slack_config()
        blocks = build_post_blocks(post, cls, config)

        actions = [b for b in blocks if b["type"] == "actions"]
        assert len(actions) == 1
        # Find link button
        link_buttons = [e for e in actions[0]["elements"] if e.get("url")]
        assert len(link_buttons) >= 1
        assert link_buttons[0]["url"] == "https://linkedin.com/posts/123"

    def test_no_linkedin_link_when_no_post_url(self):
        post = _make_post(post_url=None)
        cls = _make_classification()
        config = _slack_config()
        blocks = build_post_blocks(post, cls, config)

        actions = [b for b in blocks if b["type"] == "actions"]
        if actions:
            link_buttons = [e for e in actions[0]["elements"] if e.get("url")]
            assert len(link_buttons) == 0


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


# ===========================================================================
# Tests for feedback.py
# ===========================================================================


class TestParseFeedbackAction:
    def test_valid_useful_action(self):
        payload = {"actions": [{"value": "useful|post-1"}]}
        result = parse_feedback_action(payload)
        assert result == ("useful", "post-1")

    def test_valid_not_useful_action(self):
        payload = {"actions": [{"value": "not_useful|post-2"}]}
        result = parse_feedback_action(payload)
        assert result == ("not_useful", "post-2")

    def test_valid_mute_similar_action(self):
        payload = {"actions": [{"value": "mute_similar|post-3"}]}
        result = parse_feedback_action(payload)
        assert result == ("mute_similar", "post-3")

    def test_invalid_payload_no_actions(self):
        payload = {}
        result = parse_feedback_action(payload)
        assert result is None

    def test_invalid_payload_empty_actions(self):
        payload = {"actions": []}
        result = parse_feedback_action(payload)
        assert result is None

    def test_invalid_payload_bad_value_format(self):
        payload = {"actions": [{"value": "nopipe"}]}
        result = parse_feedback_action(payload)
        assert result is None

    def test_invalid_payload_missing_value(self):
        payload = {"actions": [{"text": "click"}]}
        result = parse_feedback_action(payload)
        assert result is None


class TestShouldAutoGenerateRule:
    def test_below_threshold(self, db_connection):
        # Insert a post and classification so FK constraints pass
        db_connection.execute(
            "INSERT INTO posts (id, author_name, post_text) VALUES (?, ?, ?)",
            ("post-1", "Author", "text"),
        )
        db_connection.execute(
            "INSERT INTO classifications (id, post_id, category, confidence, reasoning, model_used) VALUES (?, ?, ?, ?, ?, ?)",
            ("cls-1", "post-1", "Skip", 0.9, "reason", "test-model"),
        )
        # Insert 2 mute_similar feedbacks (below default threshold of 3)
        for i in range(2):
            db_connection.execute(
                "INSERT INTO user_feedback (id, post_id, classification_id, feedback_type) VALUES (?, ?, ?, ?)",
                (f"fb-{i}", "post-1", "cls-1", "mute_similar"),
            )
        db_connection.commit()

        assert should_auto_generate_rule(db_connection, "post-1") is False

    def test_at_threshold(self, db_connection):
        db_connection.execute(
            "INSERT INTO posts (id, author_name, post_text) VALUES (?, ?, ?)",
            ("post-2", "Author", "text"),
        )
        db_connection.execute(
            "INSERT INTO classifications (id, post_id, category, confidence, reasoning, model_used) VALUES (?, ?, ?, ?, ?, ?)",
            ("cls-2", "post-2", "Skip", 0.9, "reason", "test-model"),
        )
        for i in range(3):
            db_connection.execute(
                "INSERT INTO user_feedback (id, post_id, classification_id, feedback_type) VALUES (?, ?, ?, ?)",
                (f"fb2-{i}", "post-2", "cls-2", "mute_similar"),
            )
        db_connection.commit()

        assert should_auto_generate_rule(db_connection, "post-2") is True

    def test_custom_threshold(self, db_connection):
        db_connection.execute(
            "INSERT INTO posts (id, author_name, post_text) VALUES (?, ?, ?)",
            ("post-3", "Author", "text"),
        )
        db_connection.execute(
            "INSERT INTO classifications (id, post_id, category, confidence, reasoning, model_used) VALUES (?, ?, ?, ?, ?, ?)",
            ("cls-3", "post-3", "Skip", 0.9, "reason", "test-model"),
        )
        db_connection.execute(
            "INSERT INTO user_feedback (id, post_id, classification_id, feedback_type) VALUES (?, ?, ?, ?)",
            ("fb3-0", "post-3", "cls-3", "mute_similar"),
        )
        db_connection.commit()

        assert should_auto_generate_rule(db_connection, "post-3", threshold=1) is True

    def test_only_counts_mute_similar(self, db_connection):
        db_connection.execute(
            "INSERT INTO posts (id, author_name, post_text) VALUES (?, ?, ?)",
            ("post-4", "Author", "text"),
        )
        db_connection.execute(
            "INSERT INTO classifications (id, post_id, category, confidence, reasoning, model_used) VALUES (?, ?, ?, ?, ?, ?)",
            ("cls-4", "post-4", "Skip", 0.9, "reason", "test-model"),
        )
        # Insert mixed feedback types
        db_connection.execute(
            "INSERT INTO user_feedback (id, post_id, classification_id, feedback_type) VALUES (?, ?, ?, ?)",
            ("fb4-0", "post-4", "cls-4", "useful"),
        )
        db_connection.execute(
            "INSERT INTO user_feedback (id, post_id, classification_id, feedback_type) VALUES (?, ?, ?, ?)",
            ("fb4-1", "post-4", "cls-4", "not_useful"),
        )
        db_connection.execute(
            "INSERT INTO user_feedback (id, post_id, classification_id, feedback_type) VALUES (?, ?, ?, ?)",
            ("fb4-2", "post-4", "cls-4", "mute_similar"),
        )
        db_connection.commit()

        # Only 1 mute_similar, threshold=3 by default
        assert should_auto_generate_rule(db_connection, "post-4") is False


class TestGenerateMuteRule:
    def test_returns_dict_with_expected_keys(self):
        post = _make_post(post_text="Excited to share that I just got promoted! #blessed #hustle")
        rule = generate_mute_rule(post, "mute-humble-brag")

        assert isinstance(rule, dict)
        assert rule["rule_name"] == "mute-humble-brag"
        assert "patterns" in rule
        assert isinstance(rule["patterns"], list)
        assert len(rule["patterns"]) > 0

    def test_rule_includes_author_info(self):
        post = _make_post(author_name="Jane Doe")
        rule = generate_mute_rule(post, "mute-jane")

        assert rule["author_name"] == "Jane Doe"

    def test_rule_name_preserved(self):
        post = _make_post()
        rule = generate_mute_rule(post, "custom-rule-name")
        assert rule["rule_name"] == "custom-rule-name"
