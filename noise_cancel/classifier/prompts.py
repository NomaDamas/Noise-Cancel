from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from noise_cancel.models import Post


def build_system_prompt(categories: list[dict], rules: list[dict]) -> str:
    lines = [
        "You are a LinkedIn feed classifier. Classify each post into exactly one category.",
        "",
        "## Categories",
    ]
    for cat in categories:
        lines.append(f"- **{cat['name']}**: {cat['description']}")

    if rules:
        lines.append("")
        lines.append("## Rules")
        lines.append("Apply these rules when matching conditions are met:")
        for rule in rules:
            conditions = rule.get("conditions", {})
            cond_parts = []
            if "keywords" in conditions:
                cond_parts.append(f"keywords: {conditions['keywords']}")
            if "text_contains_any" in conditions:
                cond_parts.append(f"text contains any of: {conditions['text_contains_any']}")
            if "author_contains" in conditions:
                cond_parts.append(f"author contains: {conditions['author_contains']}")
            cond_str = "; ".join(cond_parts)
            lines.append(
                f"- **{rule['name']}** ({rule['type']}, priority {rule.get('priority', 0)}): "
                f"if {cond_str} -> {rule['target_category']}"
            )

    lines.append("")
    lines.append("## Instructions")
    lines.append("For each post, provide: category, confidence (0.0-1.0), reasoning, and any applied rule names.")
    lines.append("Use the classify_posts tool to return your classifications.")

    return "\n".join(lines)


def build_user_prompt(posts: list[Post]) -> str:
    lines = ["Classify the following posts:", ""]
    for i, post in enumerate(posts):
        lines.append(f"### Post {i}")
        lines.append(f"**Author**: {post.author_name}")
        lines.append(f"**Text**: {post.post_text}")
        lines.append("")
    return "\n".join(lines)


def check_rule_match(post: Post, rule: dict) -> bool:
    conditions = rule.get("conditions", {})
    if not conditions:
        return False

    matched = False
    text_lower = post.post_text.lower()
    author_lower = post.author_name.lower()

    if "keywords" in conditions:
        for kw in conditions["keywords"]:
            if kw.lower() in text_lower:
                matched = True
                break

    if "text_contains_any" in conditions:
        for phrase in conditions["text_contains_any"]:
            if phrase.lower() in text_lower:
                matched = True
                break

    if "author_contains" in conditions and conditions["author_contains"].lower() in author_lower:
        matched = True

    return matched
