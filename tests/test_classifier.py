from __future__ import annotations

import json
import re
from unittest.mock import MagicMock, patch

from noise_cancel.classifier.schemas import BatchClassificationResult, PostClassification
from noise_cancel.config import AppConfig
from noise_cancel.models import Post

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_post(
    index: int = 0,
    text: str = "Hello world",
    author: str = "Alice",
    platform: str = "linkedin",
) -> Post:
    return Post(
        id=f"post-{index}",
        platform=platform,
        author_name=author,
        post_text=text,
    )


def _make_config(**overrides) -> AppConfig:
    classifier = {
        "model": "claude-sonnet-4-6",
        "batch_size": 5,
        "temperature": 0.0,
        "categories": [
            {
                "name": "Read",
                "description": "Worth reading - valuable insights, relevant industry news, useful knowledge",
                "emoji": ":fire:",
            },
            {
                "name": "Skip",
                "description": "Not worth reading - engagement bait, humble brag, ads, spam, irrelevant",
                "emoji": ":mute:",
            },
        ],
        "whitelist": {
            "keywords": [r"(?i)research paper", r"(?i)\barxiv\b"],
            "authors": [r"(?i)yann lecun"],
        },
        "blacklist": {
            "keywords": [r"(?i)agree\?", r"(?i)thoughts\?", r"(?i)like if you"],
            "authors": [],
        },
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
            category="Read",
            confidence=0.95,
            reasoning="Very relevant content",
        )
        assert pc.post_index == 0
        assert pc.category == "Read"
        assert pc.confidence == 0.95
        assert pc.reasoning == "Very relevant content"
        assert pc.applied_rules == []

    def test_with_applied_rules(self):
        pc = PostClassification(
            post_index=1,
            category="Read",
            confidence=0.8,
            reasoning="Whitelisted keyword match",
            applied_rules=["whitelist"],
        )
        assert pc.applied_rules == ["whitelist"]

    def test_confidence_boundaries(self):
        pc_low = PostClassification(post_index=0, category="Skip", confidence=0.0, reasoning="r")
        pc_high = PostClassification(post_index=0, category="Skip", confidence=1.0, reasoning="r")
        assert pc_low.confidence == 0.0
        assert pc_high.confidence == 1.0


class TestBatchClassificationResult:
    def test_empty_batch(self):
        result = BatchClassificationResult(classifications=[])
        assert result.classifications == []

    def test_multiple_classifications(self):
        items = [PostClassification(post_index=i, category="Skip", confidence=0.5, reasoning="r") for i in range(3)]
        result = BatchClassificationResult(classifications=items)
        assert len(result.classifications) == 3
        assert result.classifications[1].post_index == 1

    def test_json_roundtrip(self):
        pc = PostClassification(post_index=0, category="Read", confidence=0.9, reasoning="good")
        result = BatchClassificationResult(classifications=[pc])
        data = json.loads(result.model_dump_json())
        restored = BatchClassificationResult(**data)
        assert restored.classifications[0].category == "Read"


# ===========================================================================
# Prompt tests
# ===========================================================================


class TestBuildSystemPrompt:
    def test_contains_categories(self):
        from noise_cancel.classifier.prompts import build_system_prompt

        categories = [
            {"name": "Read", "description": "Worth reading - valuable insights", "emoji": ":fire:"},
            {"name": "Skip", "description": "Not worth reading", "emoji": ":mute:"},
        ]
        prompt = build_system_prompt(categories=categories)
        assert "Read" in prompt
        assert "Worth reading - valuable insights" in prompt
        assert "Skip" in prompt

    def test_does_not_include_rule_keyword_lists(self):
        from noise_cancel.classifier.prompts import build_system_prompt

        prompt = build_system_prompt(
            categories=[],
            whitelist={"keywords": [r"(?i)\barxiv\b"], "authors": [r"(?i)yann lecun"]},
            blacklist={"keywords": [r"(?i)agree\?"], "authors": []},
        )
        assert "Override Rules" not in prompt
        assert "Always classify as **Read**" not in prompt
        assert "Always classify as **Skip**" not in prompt
        assert r"(?i)\barxiv\b" not in prompt
        assert r"(?i)agree\?" not in prompt

    def test_empty_lists(self):
        from noise_cancel.classifier.prompts import build_system_prompt

        prompt = build_system_prompt(categories=[])
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "Override Rules" not in prompt

    def test_language_instruction_when_non_english(self):
        from noise_cancel.classifier.prompts import build_system_prompt

        prompt = build_system_prompt(categories=[], language="korean")
        assert "korean" in prompt
        assert "Write all summaries in korean" in prompt

    def test_no_language_instruction_when_english(self):
        from noise_cancel.classifier.prompts import build_system_prompt

        prompt = build_system_prompt(categories=[], language="english")
        assert "Write all summaries" not in prompt


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
# Whitelist / blacklist matching tests
# ===========================================================================


class TestCheckWhitelist:
    def test_keyword_group_match(self):
        from noise_cancel.classifier.prompts import check_whitelist

        post = _make_post(text="Check out this research paper on arxiv about LLMs")
        assert check_whitelist(post, {"keywords": [r"\b(arxiv|preprint)\b"], "authors": []}) is True

    def test_keyword_anchor_no_match(self):
        from noise_cancel.classifier.prompts import check_whitelist

        post = _make_post(text="FYI: AI update from the team")
        assert check_whitelist(post, {"keywords": [r"^AI update"], "authors": []}) is False

    def test_author_regex_match(self):
        from noise_cancel.classifier.prompts import check_whitelist

        post = _make_post(text="Some post", author="Yann LeCun")
        assert check_whitelist(post, {"keywords": [], "authors": [r"Yann\s+LeCun"]}) is True

    def test_regex_inline_flag_case_insensitive(self):
        from noise_cancel.classifier.prompts import check_whitelist

        post = _make_post(text="ai strategy memo")
        assert check_whitelist(post, {"keywords": [r"(?i)\bAI\b"], "authors": []}) is True

    def test_empty_whitelist(self):
        from noise_cancel.classifier.prompts import check_whitelist

        post = _make_post(text="Anything")
        assert check_whitelist(post, {"keywords": [], "authors": []}) is False

    def test_empty_dict(self):
        from noise_cancel.classifier.prompts import check_whitelist

        post = _make_post(text="Anything")
        assert check_whitelist(post, {}) is False


class TestCheckBlacklist:
    def test_keyword_match(self):
        from noise_cancel.classifier.prompts import check_blacklist

        post = _make_post(text="This is amazing, agree?")
        assert check_blacklist(post, {"keywords": [r"agree\?", r"thoughts\?"], "authors": []}) is True

    def test_keyword_no_match(self):
        from noise_cancel.classifier.prompts import check_blacklist

        post = _make_post(text="Solid technical analysis of transformers")
        assert check_blacklist(post, {"keywords": [r"agree\?", r"thoughts\?"], "authors": []}) is False

    def test_author_match(self):
        from noise_cancel.classifier.prompts import check_blacklist

        post = _make_post(text="Buy my course!", author="Spammy Steve")
        assert check_blacklist(post, {"keywords": [], "authors": [r"Spammy\s+Steve"]}) is True


# ===========================================================================
# Engine tests
# ===========================================================================


class TestPreFilterWhitelistBlacklist:
    """Whitelist/blacklist are resolved before API call in classify_posts()."""

    def test_whitelist_skips_api(self):
        from noise_cancel.classifier.engine import ClassificationEngine

        config = _make_config()
        engine = ClassificationEngine(config)
        mock_client = MagicMock()
        engine._client = mock_client

        # All posts match whitelist ("arxiv") — API should not be called
        posts = [_make_post(0, "research paper on arxiv"), _make_post(1, "new arxiv preprint")]
        results = engine.classify_posts(posts)

        assert len(results) == 2
        assert all(r.category == "Read" for r in results)
        assert all(r.applied_rules == ["whitelist"] for r in results)
        mock_client.messages.create.assert_not_called()

    def test_blacklist_skips_api(self):
        from noise_cancel.classifier.engine import ClassificationEngine

        config = _make_config()
        engine = ClassificationEngine(config)
        mock_client = MagicMock()
        engine._client = mock_client

        posts = [_make_post(0, "This is amazing, agree?")]
        results = engine.classify_posts(posts)

        assert len(results) == 1
        assert results[0].category == "Skip"
        assert results[0].applied_rules == ["blacklist"]
        mock_client.messages.create.assert_not_called()

    def test_whitelist_wins_over_blacklist(self):
        from noise_cancel.classifier.engine import ClassificationEngine

        config = _make_config()
        engine = ClassificationEngine(config)
        mock_client = MagicMock()
        engine._client = mock_client

        # Matches both whitelist ("arxiv") and blacklist ("agree?")
        posts = [_make_post(0, "research paper on arxiv, agree?")]
        results = engine.classify_posts(posts)

        assert results[0].category == "Read"
        assert results[0].applied_rules == ["whitelist"]
        mock_client.messages.create.assert_not_called()

    def test_mixed_pre_filter_and_api(self):
        from noise_cancel.classifier.engine import ClassificationEngine

        config = _make_config()
        engine = ClassificationEngine(config)
        mock_client = MagicMock()
        engine._client = mock_client

        # Post 0: whitelist match (no API), Post 1: no match (API), Post 2: blacklist match (no API)
        mock_tool_block = MagicMock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.input = {
            "classifications": [{"post_index": 0, "category": "Read", "confidence": 0.7, "reasoning": "decent"}]
        }
        mock_response = MagicMock()
        mock_response.content = [mock_tool_block]
        mock_client.messages.create.return_value = mock_response

        posts = [
            _make_post(0, "new arxiv paper on LLMs"),
            _make_post(1, "Normal post about databases"),
            _make_post(2, "Like if you agree with me"),
        ]
        results = engine.classify_posts(posts)

        assert len(results) == 3
        assert results[0].category == "Read"
        assert results[0].applied_rules == ["whitelist"]
        assert results[1].category == "Read"
        assert results[1].applied_rules == []
        assert results[2].category == "Skip"
        assert results[2].applied_rules == ["blacklist"]
        # Only 1 API call for the 1 unmatched post
        mock_client.messages.create.assert_called_once()

    def test_no_match_all_go_to_api(self):
        from noise_cancel.classifier.engine import ClassificationEngine

        config = _make_config(whitelist={"keywords": [], "authors": []}, blacklist={"keywords": [], "authors": []})
        engine = ClassificationEngine(config)
        mock_client = MagicMock()
        engine._client = mock_client

        mock_tool_block = MagicMock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.input = {
            "classifications": [
                {"post_index": 0, "category": "Read", "confidence": 0.8, "reasoning": "r"},
                {"post_index": 1, "category": "Skip", "confidence": 0.6, "reasoning": "r"},
            ]
        }
        mock_response = MagicMock()
        mock_response.content = [mock_tool_block]
        mock_client.messages.create.return_value = mock_response

        posts = [_make_post(0, "Normal post A"), _make_post(1, "Normal post B")]
        results = engine.classify_posts(posts)

        assert len(results) == 2
        mock_client.messages.create.assert_called_once()


class TestRegexRuleCompilation:
    def test_compiles_patterns_once(self):
        from noise_cancel.classifier.engine import ClassificationEngine

        config = _make_config(
            whitelist={"keywords": [r"\bAI\b"], "authors": [r"Yann\s+LeCun"]},
            blacklist={"keywords": [r"^Spam:"], "authors": []},
        )

        with patch("noise_cancel.classifier.engine.re.compile", wraps=re.compile) as mock_compile:
            engine = ClassificationEngine(config)
            compile_call_count = mock_compile.call_count

            # Matching should not trigger additional compilation.
            engine._apply_rules(_make_post(text="AI memo"), 0)
            engine._apply_rules(_make_post(text="No rule match"), 1)

            assert mock_compile.call_count == compile_call_count


class TestClassifyBatch:
    def test_classify_batch_calls_api(self):
        from noise_cancel.classifier.engine import ClassificationEngine

        config = _make_config()
        engine = ClassificationEngine(config)

        mock_client = MagicMock()
        engine._client = mock_client

        api_response_content = BatchClassificationResult(
            classifications=[
                PostClassification(post_index=0, category="Read", confidence=0.9, reasoning="Relevant"),
                PostClassification(post_index=1, category="Skip", confidence=0.8, reasoning="Bait"),
            ]
        )

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
        assert results[0].category == "Read"
        assert results[1].category == "Skip"
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
                {"post_index": 0, "category": "Skip", "confidence": 0.5, "reasoning": "r"},
            ]
        }
        mock_response = MagicMock()
        mock_response.content = [mock_tool_block]
        mock_response.stop_reason = "tool_use"
        mock_client.messages.create.return_value = mock_response

        engine.classify_batch([_make_post(0)])

        call_kwargs = mock_client.messages.create.call_args
        assert call_kwargs.kwargs["model"] == "claude-sonnet-4-5-20250929"

    def test_system_prompt_excludes_rule_patterns(self):
        from noise_cancel.classifier.engine import ClassificationEngine

        config = _make_config(
            whitelist={"keywords": [r"UNIQUE_WL_PATTERN"], "authors": []},
            blacklist={"keywords": [r"UNIQUE_BL_PATTERN"], "authors": []},
        )
        engine = ClassificationEngine(config)

        mock_client = MagicMock()
        engine._client = mock_client

        mock_tool_block = MagicMock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.input = {
            "classifications": [
                {"post_index": 0, "category": "Read", "confidence": 0.5, "reasoning": "r"},
            ]
        }
        mock_response = MagicMock()
        mock_response.content = [mock_tool_block]
        mock_response.stop_reason = "tool_use"
        mock_client.messages.create.return_value = mock_response

        engine.classify_batch([_make_post(0, "Normal post")])

        call_kwargs = mock_client.messages.create.call_args.kwargs
        system_prompt = call_kwargs["system"]
        assert "UNIQUE_WL_PATTERN" not in system_prompt
        assert "UNIQUE_BL_PATTERN" not in system_prompt


class TestClassifyPosts:
    def test_splits_into_batches(self):
        from noise_cancel.classifier.engine import ClassificationEngine

        config = _make_config(
            batch_size=2, whitelist={"keywords": [], "authors": []}, blacklist={"keywords": [], "authors": []}
        )
        engine = ClassificationEngine(config)

        mock_client = MagicMock()
        engine._client = mock_client

        def make_response(posts):
            classifications = [
                {"post_index": i, "category": "Skip", "confidence": 0.5, "reasoning": "r"} for i in range(len(posts))
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

    def test_classify_posts_uses_platform_specific_system_prompts(self):
        from noise_cancel.classifier.engine import ClassificationEngine

        config = _make_config(
            batch_size=10,
            whitelist={"keywords": [], "authors": []},
            blacklist={"keywords": [], "authors": []},
            platform_prompts={
                "x": {"system_prompt": "X_PLATFORM_SYSTEM_PROMPT"},
                "reddit": {"system_prompt": "REDDIT_PLATFORM_SYSTEM_PROMPT"},
            },
        )
        engine = ClassificationEngine(config)

        mock_client = MagicMock()
        engine._client = mock_client

        def make_response(batch_size: int) -> MagicMock:
            classifications = [
                {"post_index": i, "category": "Read", "confidence": 0.6, "reasoning": "r"} for i in range(batch_size)
            ]
            mock_tool_block = MagicMock()
            mock_tool_block.type = "tool_use"
            mock_tool_block.input = {"classifications": classifications}
            mock_response = MagicMock()
            mock_response.content = [mock_tool_block]
            mock_response.stop_reason = "tool_use"
            return mock_response

        # LinkedIn (default prompt), X (override), Reddit (override).
        mock_client.messages.create.side_effect = [
            make_response(1),
            make_response(2),
            make_response(1),
        ]

        posts = [
            _make_post(0, "LinkedIn post", platform="linkedin"),
            _make_post(1, "X post 1", platform="x"),
            _make_post(2, "Reddit post", platform="reddit"),
            _make_post(3, "X post 2", platform="x"),
        ]

        results = engine.classify_posts(posts)

        assert len(results) == 4
        assert mock_client.messages.create.call_count == 3

        system_prompts = [call.kwargs["system"] for call in mock_client.messages.create.call_args_list]
        assert "You are a social media feed classifier." in system_prompts[0]
        assert system_prompts[1] == "X_PLATFORM_SYSTEM_PROMPT"
        assert system_prompts[2] == "REDDIT_PLATFORM_SYSTEM_PROMPT"


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
