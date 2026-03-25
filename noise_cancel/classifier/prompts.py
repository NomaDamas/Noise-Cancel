from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from noise_cancel.models import Post


def build_system_prompt(
    categories: list[dict],
    whitelist: dict | None = None,
    blacklist: dict | None = None,
    language: str = "english",
) -> str:
    lines = [
        "You are a social media feed classifier. Classify each post into exactly one category.",
        "",
        "## Categories",
    ]
    for cat in categories:
        lines.append(f"- **{cat['name']}**: {cat['description']}")

    # Kept for backward compatibility with call sites that may still pass these.
    _ = whitelist, blacklist

    lines.append("")
    lines.append("## Examples")
    lines.append("")
    lines.append(
        '**Post**: "Just published our research on efficient transformer architectures. '
        "We found that sparse attention patterns can reduce compute by 40% while maintaining "
        'accuracy. Paper: arxiv.org/abs/..."'
    )
    lines.append("**Author**: Dr. Sarah Chen")
    lines.append("**Classification**: Read (confidence: 0.95)")
    lines.append("**Reasoning**: Original research with concrete findings and data - high-value technical content.")
    lines.append("")
    lines.append(
        "**Post**: \"Excited to announce I've been promoted to VP! "
        "\U0001f389 Hard work pays off. Who else got promoted this year? "
        'Drop a \U0001f64c below!"'
    )
    lines.append("**Author**: Marketing Mike")
    lines.append("**Classification**: Skip (confidence: 0.90)")
    lines.append("**Reasoning**: Personal achievement humble brag with engagement bait question.")
    lines.append("")
    lines.append('**Post**: "5 AI tools that will 10x your productivity (Thread \U0001f9f5\U0001f447)"')
    lines.append("**Author**: Growth Guru")
    lines.append("**Classification**: Skip (confidence: 0.85)")
    lines.append("**Reasoning**: Clickbait thread format with exaggerated productivity claims.")
    lines.append("")
    lines.append(
        '**Post**: "[r/MachineLearning] We benchmarked LoRA vs full fine-tuning on Llama 3 '
        "across 8 downstream tasks. LoRA matched full FT on 6/8 while using 12x less memory. "
        'Code + results in repo."'
    )
    lines.append("**Author**: u/ml_researcher_42")
    lines.append("**Classification**: Read (confidence: 0.92)")
    lines.append("**Reasoning**: Reproducible benchmark comparison with concrete results and shared code.")
    lines.append("")
    lines.append(
        '**Post**: "OpenAI just dropped GPT-5. Early benchmarks look insane. '
        'This changes everything for agents. Curious what others think."'
    )
    lines.append("**Author**: @ai_observer")
    lines.append("**Classification**: Read (confidence: 0.70)")
    lines.append("**Reasoning**: Short-form breaking news commentary — informational but light on substance.")

    lines.append("")
    lines.append("## Instructions")
    lines.append("For each post, provide: category, confidence (0.0-1.0), and reasoning.")
    lines.append("For each post, also provide a 'summary': a concise 2-3 sentence summary of the post content.")
    if language != "english":
        lines.append(
            f"IMPORTANT: Write all summaries in {language}, even if the original post is in a different language."
        )
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


def _matches(post: Post, rule: dict) -> bool:
    keywords = rule.get("keywords", []) if isinstance(rule, dict) else []
    authors = rule.get("authors", []) if isinstance(rule, dict) else []

    if any(isinstance(pattern, str) and re.search(pattern, post.post_text) for pattern in keywords):
        return True
    return any(isinstance(pattern, str) and re.search(pattern, post.author_name) for pattern in authors)


def check_whitelist(post: Post, whitelist: dict) -> bool:
    """Return True if the post matches any whitelist condition."""
    return _matches(post, whitelist)


def check_blacklist(post: Post, blacklist: dict) -> bool:
    """Return True if the post matches any blacklist condition."""
    return _matches(post, blacklist)
