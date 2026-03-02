from __future__ import annotations

import re
from importlib import import_module
from typing import TYPE_CHECKING

from noise_cancel.classifier.prompts import build_system_prompt, build_user_prompt
from noise_cancel.classifier.schemas import BatchClassificationResult, PostClassification
from noise_cancel.config import ConfigError

if TYPE_CHECKING:
    from noise_cancel.config import AppConfig
    from noise_cancel.models import Post


class ClassificationEngine:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._client = None
        classifier_cfg = self._config.classifier
        self._whitelist_patterns = self._compile_rule_patterns(
            "whitelist",
            classifier_cfg.get("whitelist", {}),
        )
        self._blacklist_patterns = self._compile_rule_patterns(
            "blacklist",
            classifier_cfg.get("blacklist", {}),
        )

    def _compile_pattern_list(self, patterns: object, *, field_path: str) -> list[re.Pattern[str]]:
        if not isinstance(patterns, list):
            return []

        compiled: list[re.Pattern[str]] = []
        for pattern in patterns:
            if not isinstance(pattern, str):
                continue
            try:
                compiled.append(re.compile(pattern))
            except re.error as exc:
                raise ConfigError.invalid_regex(
                    field_path=field_path,
                    pattern=pattern,
                    detail=str(exc),
                ) from exc
        return compiled

    def _compile_rule_patterns(
        self,
        rule_name: str,
        rule: dict[str, object] | None,
    ) -> dict[str, list[re.Pattern[str]]]:
        if rule is None:
            return {"keywords": [], "authors": []}
        return {
            "keywords": self._compile_pattern_list(
                rule.get("keywords", []),
                field_path=f"classifier.{rule_name}.keywords",
            ),
            "authors": self._compile_pattern_list(
                rule.get("authors", []),
                field_path=f"classifier.{rule_name}.authors",
            ),
        }

    def _matches_rule(self, post: Post, rule: dict[str, list[re.Pattern[str]]]) -> bool:
        if any(pattern.search(post.post_text) for pattern in rule["keywords"]):
            return True
        return any(pattern.search(post.author_name) for pattern in rule["authors"])

    def _apply_rules(self, post: Post, post_index: int) -> PostClassification | None:
        if self._matches_rule(post, self._whitelist_patterns):
            return PostClassification(
                post_index=post_index,
                category="Read",
                confidence=1.0,
                reasoning="Matched whitelist",
                applied_rules=["whitelist"],
            )
        if self._matches_rule(post, self._blacklist_patterns):
            return PostClassification(
                post_index=post_index,
                category="Skip",
                confidence=1.0,
                reasoning="Matched blacklist",
                applied_rules=["blacklist"],
            )
        return None

    def _get_client(self):
        if self._client is not None:
            return self._client
        anthropic = import_module("anthropic")
        self._client = anthropic.Anthropic()
        return self._client

    def classify_batch(self, posts: list[Post]) -> list[PostClassification]:
        """Classify a batch of posts via Claude API. No whitelist/blacklist filtering here."""
        client = self._get_client()
        cfg = self._config.classifier
        categories = cfg.get("categories", [])

        language = self._config.general.get("language", "english")
        system_prompt = build_system_prompt(categories, language=language)
        user_prompt = build_user_prompt(posts)

        tool_schema = BatchClassificationResult.model_json_schema()

        response = client.messages.create(
            model=cfg["model"],
            max_tokens=4096,
            temperature=cfg.get("temperature", 0.0),
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            tools=[
                {
                    "name": "classify_posts",
                    "description": "Return classification results for the batch of posts.",
                    "input_schema": tool_schema,
                }
            ],
            tool_choice={"type": "tool", "name": "classify_posts"},
        )

        for block in response.content:
            if block.type == "tool_use":
                result = BatchClassificationResult(**block.input)
                return result.classifications

        return []

    def classify_posts(self, posts: list[Post]) -> list[PostClassification]:
        """Classify posts. Whitelist/blacklist are resolved first; only unmatched posts hit the API."""
        if not posts:
            return []

        cfg = self._config.classifier

        results: list[PostClassification | None] = [None] * len(posts)
        needs_api: list[tuple[int, Post]] = []

        for i, post in enumerate(posts):
            rule_result = self._apply_rules(post, i)
            if rule_result is not None:
                results[i] = rule_result
            else:
                needs_api.append((i, post))

        # Only call API for posts not caught by whitelist/blacklist
        if needs_api:
            batch_size = cfg.get("batch_size", 10)
            api_posts = [post for _, post in needs_api]

            api_results: list[PostClassification] = []
            for start in range(0, len(api_posts), batch_size):
                batch = api_posts[start : start + batch_size]
                api_results.extend(self.classify_batch(batch))

            # Map API results back to original indices
            for (original_idx, _), api_cls in zip(needs_api, api_results, strict=True):
                results[original_idx] = PostClassification(
                    post_index=original_idx,
                    category=api_cls.category,
                    confidence=api_cls.confidence,
                    reasoning=api_cls.reasoning,
                    summary=api_cls.summary,
                )

        return [r for r in results if r is not None]
