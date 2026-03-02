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
        self._default_system_prompt = self._build_default_system_prompt()
        self._platform_prompt_overrides = self._load_platform_prompt_overrides(classifier_cfg.get("platform_prompts"))
        self._whitelist_patterns = self._compile_rule_patterns(
            "whitelist",
            classifier_cfg.get("whitelist", {}),
        )
        self._blacklist_patterns = self._compile_rule_patterns(
            "blacklist",
            classifier_cfg.get("blacklist", {}),
        )

    def _build_default_system_prompt(self) -> str:
        classifier_cfg = self._config.classifier
        categories = classifier_cfg.get("categories", [])
        language = self._config.general.get("language", "english")
        return build_system_prompt(categories, language=language)

    def _normalize_platform(self, platform: object) -> str:
        if not isinstance(platform, str):
            return ""
        return platform.strip().lower()

    def _load_platform_prompt_overrides(self, platform_prompts: object) -> dict[str, str]:
        if not isinstance(platform_prompts, dict):
            return {}

        overrides: dict[str, str] = {}
        for platform, prompt_config in platform_prompts.items():
            normalized_platform = self._normalize_platform(platform)
            if not normalized_platform or not isinstance(prompt_config, dict):
                continue
            prompt_fields = {key: value for key, value in prompt_config.items() if isinstance(key, str)}
            system_prompt = prompt_fields.get("system_prompt")
            if isinstance(system_prompt, str) and system_prompt:
                overrides[normalized_platform] = system_prompt
        return overrides

    def _system_prompt_for_platform(self, platform: str) -> str:
        return self._platform_prompt_overrides.get(platform, self._default_system_prompt)

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

    def classify_batch(
        self,
        posts: list[Post],
        *,
        system_prompt: str | None = None,
    ) -> list[PostClassification]:
        """Classify a batch of posts via Claude API. No whitelist/blacklist filtering here."""
        client = self._get_client()
        cfg = self._config.classifier
        user_prompt = build_user_prompt(posts)
        prompt_to_use = system_prompt or self._default_system_prompt

        tool_schema = BatchClassificationResult.model_json_schema()

        response = client.messages.create(
            model=cfg["model"],
            max_tokens=4096,
            temperature=cfg.get("temperature", 0.0),
            system=prompt_to_use,
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
        needs_api_by_platform: dict[str, list[tuple[int, Post]]] = {}

        for i, post in enumerate(posts):
            rule_result = self._apply_rules(post, i)
            if rule_result is not None:
                results[i] = rule_result
            else:
                platform = self._normalize_platform(post.platform)
                needs_api_by_platform.setdefault(platform, []).append((i, post))

        # Only call API for posts not caught by whitelist/blacklist
        if needs_api_by_platform:
            batch_size = cfg.get("batch_size", 10)

            for platform, indexed_posts in needs_api_by_platform.items():
                system_prompt = self._system_prompt_for_platform(platform)
                for start in range(0, len(indexed_posts), batch_size):
                    indexed_batch = indexed_posts[start : start + batch_size]
                    batch = [post for _, post in indexed_batch]
                    api_results = self.classify_batch(batch, system_prompt=system_prompt)

                    # Map API results back to original indices for this platform-specific batch.
                    for (original_idx, _), api_cls in zip(indexed_batch, api_results, strict=True):
                        results[original_idx] = PostClassification(
                            post_index=original_idx,
                            category=api_cls.category,
                            confidence=api_cls.confidence,
                            reasoning=api_cls.reasoning,
                            summary=api_cls.summary,
                        )

        return [r for r in results if r is not None]
