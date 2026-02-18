from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

from noise_cancel.classifier.prompts import build_system_prompt, build_user_prompt, check_rule_match
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
        client = self._get_client()
        cfg = self._config.classifier
        categories = cfg.get("categories", [])
        rules = cfg.get("rules", [])

        system_prompt = build_system_prompt(categories, rules)
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
                classifications = result.classifications
                return [self.apply_rule_overrides(posts[c.post_index], c, rules) for c in classifications]

        return []

    def classify_posts(self, posts: list[Post]) -> list[PostClassification]:
        if not posts:
            return []

        batch_size = self._config.classifier.get("batch_size", 10)
        all_results: list[PostClassification] = []

        for start in range(0, len(posts), batch_size):
            batch = posts[start : start + batch_size]
            results = self.classify_batch(batch)
            all_results.extend(results)

        return all_results

    def apply_rule_overrides(
        self, post: Post, classification: PostClassification, rules: list[dict]
    ) -> PostClassification:
        matching_rules = []
        for rule in rules:
            if check_rule_match(post, rule):
                matching_rules.append(rule)

        if not matching_rules:
            return classification

        best_rule = max(matching_rules, key=lambda r: r.get("priority", 0))

        return PostClassification(
            post_index=classification.post_index,
            category=best_rule["target_category"],
            confidence=classification.confidence,
            reasoning=classification.reasoning,
            applied_rules=[r["name"] for r in matching_rules],
        )
