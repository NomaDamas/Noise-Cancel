from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

from noise_cancel.classifier.prompts import build_system_prompt, build_user_prompt, check_blacklist, check_whitelist
from noise_cancel.classifier.schemas import BatchClassificationResult, PostClassification

if TYPE_CHECKING:
    from noise_cancel.config import AppConfig
    from noise_cancel.models import Post


class ClassificationEngine:
    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._client = None

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
        whitelist = cfg.get("whitelist", {})
        blacklist = cfg.get("blacklist", {})

        system_prompt = build_system_prompt(categories, whitelist, blacklist)
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
        whitelist = cfg.get("whitelist", {})
        blacklist = cfg.get("blacklist", {})

        results: list[PostClassification | None] = [None] * len(posts)
        needs_api: list[tuple[int, Post]] = []

        for i, post in enumerate(posts):
            if check_whitelist(post, whitelist):
                results[i] = PostClassification(
                    post_index=i,
                    category="Read",
                    confidence=1.0,
                    reasoning="Matched whitelist",
                    applied_rules=["whitelist"],
                )
            elif check_blacklist(post, blacklist):
                results[i] = PostClassification(
                    post_index=i,
                    category="Skip",
                    confidence=1.0,
                    reasoning="Matched blacklist",
                    applied_rules=["blacklist"],
                )
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
                )

        return [r for r in results if r is not None]
