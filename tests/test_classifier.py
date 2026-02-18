from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from noise_cancel.classifier.schemas import BatchClassificationResult, PostClassification
from noise_cancel.config import AppConfig
from noise_cancel.models import Post

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_post(index: int = 0, text: str = "Hello world", author: str = "Alice") -> Post:
    return Post(
        id=f"post-{index}",
        author_name=author,
        post_text=text,
    )


def _make_config(**overrides) -> AppConfig:
    classifier = {
        "model": "claude-haiku-4-5-20251001",
        "batch_size": 5,
        "temperature": 0.0,
        "categories": [
            {"name": "Must Read", "description": "High-value content", "emoji": ":fire:"},
            {"name": "Interesting", "description": "Worth a quick look", "emoji": ":eyes:"},
            {"name": "Noise", "description": "Engagement bait", "emoji": ":mute:"},
            {"name": "Spam", "description": "Ads, irrelevant", "emoji": ":no_entry:"},
        ],
        "rules": [
            {
                "name": "prioritize_ai_research",
                "type": "boost",
                "conditions": {"keywords": ["research paper", "arxiv"]},
                "target_category": "Must Read",
                "priority": 10,
            },
            {
                "name": "suppress_engagement_bait",
                "type": "suppress",
                "conditions": {"text_contains_any": ["agree?", "thoughts?", "like if you"]},
                "target_category": "Noise",
                "priority": 5,
            },
            {
                "name": "boost_from_author",
                "type": "boost",
                "conditions": {"author_contains": "Yann LeCun"},
                "target_category": "Must Read",
                "priority": 8,
            },
        ],
    }
    classifier.update(overrides)
    return AppConfig(
        general={"data_dir": "/tmp/nc-test", "max_posts_per_run": 50},  # noqa: S108
        classifier=classifier,
    )


# ===========================================================================
# Schema tests
# ===========================================================================


class TestPostClassification:
    def test_valid_classification(self):
        pc = PostClassification(
            post_index=0,
            category="Must Read",
            confidence=0.95,
            reasoning="Very relevant content",
        )
        assert pc.post_index == 0
        assert pc.category == "Must Read"
        assert pc.confidence == 0.95
        assert pc.reasoning == "Very relevant content"
        assert pc.applied_rules == []

    def test_with_applied_rules(self):
        pc = PostClassification(
            post_index=1,
            category="Noise",
            confidence=0.8,
            reasoning="Engagement bait detected",
            applied_rules=["suppress_engagement_bait"],
        )
        assert pc.applied_rules == ["suppress_engagement_bait"]

    def test_confidence_boundaries(self):
        pc_low = PostClassification(post_index=0, category="Spam", confidence=0.0, reasoning="r")
        pc_high = PostClassification(post_index=0, category="Spam", confidence=1.0, reasoning="r")
        assert pc_low.confidence == 0.0
        assert pc_high.confidence == 1.0


class TestBatchClassificationResult:
    def test_empty_batch(self):
        result = BatchClassificationResult(classifications=[])
        assert result.classifications == []

    def test_multiple_classifications(self):
        items = [PostClassification(post_index=i, category="Noise", confidence=0.5, reasoning="r") for i in range(3)]
        result = BatchClassificationResult(classifications=items)
        assert len(result.classifications) == 3
        assert result.classifications[1].post_index == 1

    def test_json_roundtrip(self):
        pc = PostClassification(post_index=0, category="Must Read", confidence=0.9, reasoning="good")
        result = BatchClassificationResult(classifications=[pc])
        data = json.loads(result.model_dump_json())
        restored = BatchClassificationResult(**data)
        assert restored.classifications[0].category == "Must Read"


# ===========================================================================
# Prompt tests
# ===========================================================================


class TestBuildSystemPrompt:
    def test_contains_categories(self):
        from noise_cancel.classifier.prompts import build_system_prompt

        categories = [
            {"name": "Must Read", "description": "High-value content", "emoji": ":fire:"},
            {"name": "Spam", "description": "Ads", "emoji": ":no_entry:"},
        ]
        prompt = build_system_prompt(categories=categories, rules=[])
        assert "Must Read" in prompt
        assert "High-value content" in prompt
        assert "Spam" in prompt

    def test_contains_rules(self):
        from noise_cancel.classifier.prompts import build_system_prompt

        rules = [
            {
                "name": "boost_ai",
                "type": "boost",
                "conditions": {"keywords": ["arxiv"]},
                "target_category": "Must Read",
                "priority": 10,
            },
        ]
        prompt = build_system_prompt(categories=[], rules=rules)
        assert "boost_ai" in prompt
        assert "arxiv" in prompt

    def test_empty_rules(self):
        from noise_cancel.classifier.prompts import build_system_prompt

        prompt = build_system_prompt(categories=[], rules=[])
        assert isinstance(prompt, str)
        assert len(prompt) > 0


class TestBuildUserPrompt:
    def test_posts_indexed(self):
        from noise_cancel.classifier.prompts import build_user_prompt

        posts = [_make_post(0, "First post"), _make_post(1, "Second post")]
        prompt = build_user_prompt(posts)
        assert "0" in prompt
        assert "First post" in prompt
        assert "1" in prompt
        assert "Second post" in prompt

    def test_includes_author(self):
        from noise_cancel.classifier.prompts import build_user_prompt

        posts = [_make_post(0, "content", author="Bob Smith")]
        prompt = build_user_prompt(posts)
        assert "Bob Smith" in prompt

    def test_single_post(self):
        from noise_cancel.classifier.prompts import build_user_prompt

        posts = [_make_post(0, "Only one")]
        prompt = build_user_prompt(posts)
        assert "Only one" in prompt


# ===========================================================================
# Rule matching tests
# ===========================================================================


class TestCheckRuleMatch:
    def test_keywords_match(self):
        from noise_cancel.classifier.prompts import check_rule_match

        post = _make_post(text="Check out this research paper on arxiv about LLMs")
        rule = {
            "name": "boost_ai",
            "type": "boost",
            "conditions": {"keywords": ["research paper", "arxiv"]},
            "target_category": "Must Read",
            "priority": 10,
        }
        assert check_rule_match(post, rule) is True

    def test_keywords_no_match(self):
        from noise_cancel.classifier.prompts import check_rule_match

        post = _make_post(text="Just a normal post about cooking")
        rule = {
            "name": "boost_ai",
            "type": "boost",
            "conditions": {"keywords": ["research paper", "arxiv"]},
            "target_category": "Must Read",
            "priority": 10,
        }
        assert check_rule_match(post, rule) is False

    def test_text_contains_any_match(self):
        from noise_cancel.classifier.prompts import check_rule_match

        post = _make_post(text="This is amazing, agree?")
        rule = {
            "name": "suppress_bait",
            "type": "suppress",
            "conditions": {"text_contains_any": ["agree?", "thoughts?"]},
            "target_category": "Noise",
            "priority": 5,
        }
        assert check_rule_match(post, rule) is True

    def test_text_contains_any_no_match(self):
        from noise_cancel.classifier.prompts import check_rule_match

        post = _make_post(text="Solid technical analysis of transformers")
        rule = {
            "name": "suppress_bait",
            "type": "suppress",
            "conditions": {"text_contains_any": ["agree?", "thoughts?"]},
            "target_category": "Noise",
            "priority": 5,
        }
        assert check_rule_match(post, rule) is False

    def test_author_contains_match(self):
        from noise_cancel.classifier.prompts import check_rule_match

        post = _make_post(text="Some post", author="Yann LeCun")
        rule = {
            "name": "boost_author",
            "type": "boost",
            "conditions": {"author_contains": "Yann LeCun"},
            "target_category": "Must Read",
            "priority": 8,
        }
        assert check_rule_match(post, rule) is True

    def test_author_contains_case_insensitive(self):
        from noise_cancel.classifier.prompts import check_rule_match

        post = _make_post(text="Some post", author="yann lecun")
        rule = {
            "name": "boost_author",
            "type": "boost",
            "conditions": {"author_contains": "Yann LeCun"},
            "target_category": "Must Read",
            "priority": 8,
        }
        assert check_rule_match(post, rule) is True

    def test_no_conditions(self):
        from noise_cancel.classifier.prompts import check_rule_match

        post = _make_post(text="Anything")
        rule = {"name": "empty", "type": "boost", "conditions": {}, "target_category": "Must Read", "priority": 1}
        assert check_rule_match(post, rule) is False


# ===========================================================================
# Engine tests
# ===========================================================================


class TestApplyRuleOverrides:
    def test_boost_rule_overrides_category(self):
        from noise_cancel.classifier.engine import ClassificationEngine

        config = _make_config()
        engine = ClassificationEngine(config)
        post = _make_post(text="New research paper on arxiv about LLMs")
        classification = PostClassification(
            post_index=0,
            category="Interesting",
            confidence=0.7,
            reasoning="Somewhat relevant",
        )
        rules = config.classifier["rules"]
        result = engine.apply_rule_overrides(post, classification, rules)
        assert result.category == "Must Read"
        assert "prioritize_ai_research" in result.applied_rules

    def test_suppress_rule_overrides_category(self):
        from noise_cancel.classifier.engine import ClassificationEngine

        config = _make_config()
        engine = ClassificationEngine(config)
        post = _make_post(text="This is so great, agree?")
        classification = PostClassification(
            post_index=0,
            category="Interesting",
            confidence=0.6,
            reasoning="Seems interesting",
        )
        rules = config.classifier["rules"]
        result = engine.apply_rule_overrides(post, classification, rules)
        assert result.category == "Noise"
        assert "suppress_engagement_bait" in result.applied_rules

    def test_no_matching_rules(self):
        from noise_cancel.classifier.engine import ClassificationEngine

        config = _make_config()
        engine = ClassificationEngine(config)
        post = _make_post(text="Normal technical post about databases")
        classification = PostClassification(
            post_index=0,
            category="Interesting",
            confidence=0.75,
            reasoning="Good content",
        )
        rules = config.classifier["rules"]
        result = engine.apply_rule_overrides(post, classification, rules)
        assert result.category == "Interesting"
        assert result.applied_rules == []

    def test_highest_priority_rule_wins(self):
        from noise_cancel.classifier.engine import ClassificationEngine

        config = _make_config()
        engine = ClassificationEngine(config)
        # Post matches both boost (priority 10) and suppress (priority 5)
        post = _make_post(text="research paper on arxiv, agree?")
        classification = PostClassification(
            post_index=0,
            category="Interesting",
            confidence=0.6,
            reasoning="Mixed",
        )
        rules = config.classifier["rules"]
        result = engine.apply_rule_overrides(post, classification, rules)
        # Boost rule has priority 10 > suppress priority 5
        assert result.category == "Must Read"


class TestClassifyBatch:
    def test_classify_batch_calls_api(self):
        from noise_cancel.classifier.engine import ClassificationEngine

        config = _make_config()
        engine = ClassificationEngine(config)

        mock_client = MagicMock()
        engine._client = mock_client

        api_response_content = BatchClassificationResult(
            classifications=[
                PostClassification(post_index=0, category="Must Read", confidence=0.9, reasoning="Relevant"),
                PostClassification(post_index=1, category="Noise", confidence=0.8, reasoning="Bait"),
            ]
        )

        # Mock the tool use response from Claude API
        mock_tool_block = MagicMock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.input = json.loads(api_response_content.model_dump_json())

        mock_response = MagicMock()
        mock_response.content = [mock_tool_block]
        mock_response.stop_reason = "tool_use"

        mock_client.messages.create.return_value = mock_response

        posts = [_make_post(0, "AI research paper"), _make_post(1, "Like if you agree?")]
        results = engine.classify_batch(posts)

        assert len(results) == 2
        assert results[0].category == "Must Read"
        assert results[1].category == "Noise"
        mock_client.messages.create.assert_called_once()

    def test_classify_batch_uses_config_model(self):
        from noise_cancel.classifier.engine import ClassificationEngine

        config = _make_config(model="claude-sonnet-4-5-20250929")
        engine = ClassificationEngine(config)

        mock_client = MagicMock()
        engine._client = mock_client

        mock_tool_block = MagicMock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.input = {
            "classifications": [
                {"post_index": 0, "category": "Noise", "confidence": 0.5, "reasoning": "r"},
            ]
        }
        mock_response = MagicMock()
        mock_response.content = [mock_tool_block]
        mock_response.stop_reason = "tool_use"
        mock_client.messages.create.return_value = mock_response

        engine.classify_batch([_make_post(0)])

        call_kwargs = mock_client.messages.create.call_args
        assert call_kwargs.kwargs["model"] == "claude-sonnet-4-5-20250929"


class TestClassifyPosts:
    def test_splits_into_batches(self):
        from noise_cancel.classifier.engine import ClassificationEngine

        config = _make_config(batch_size=2)
        engine = ClassificationEngine(config)

        mock_client = MagicMock()
        engine._client = mock_client

        def make_response(posts):
            classifications = [
                {"post_index": i, "category": "Noise", "confidence": 0.5, "reasoning": "r"} for i in range(len(posts))
            ]
            mock_tool_block = MagicMock()
            mock_tool_block.type = "tool_use"
            mock_tool_block.input = {"classifications": classifications}
            mock_response = MagicMock()
            mock_response.content = [mock_tool_block]
            mock_response.stop_reason = "tool_use"
            return mock_response

        # 5 posts with batch_size=2 => 3 batches (2, 2, 1)
        mock_client.messages.create.side_effect = [
            make_response([None, None]),
            make_response([None, None]),
            make_response([None]),
        ]

        posts = [_make_post(i) for i in range(5)]
        results = engine.classify_posts(posts)

        assert len(results) == 5
        assert mock_client.messages.create.call_count == 3

    def test_empty_posts_returns_empty(self):
        from noise_cancel.classifier.engine import ClassificationEngine

        config = _make_config()
        engine = ClassificationEngine(config)
        results = engine.classify_posts([])
        assert results == []


class TestLazyClient:
    def test_get_client_creates_anthropic_client(self):
        from noise_cancel.classifier.engine import ClassificationEngine

        config = _make_config()
        engine = ClassificationEngine(config)
        assert engine._client is None

        with patch("noise_cancel.classifier.engine.import_module") as mock_import:
            mock_anthropic_module = MagicMock()
            mock_import.return_value = mock_anthropic_module
            client = engine._get_client()
            mock_anthropic_module.Anthropic.assert_called_once()
            assert client is not None

    def test_get_client_returns_cached(self):
        from noise_cancel.classifier.engine import ClassificationEngine

        config = _make_config()
        engine = ClassificationEngine(config)

        mock_client = MagicMock()
        engine._client = mock_client
        assert engine._get_client() is mock_client
