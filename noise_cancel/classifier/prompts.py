from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from noise_cancel.models import Post


def build_system_prompt(
    categories: list[dict],
    whitelist: dict | None = None,
    blacklist: dict | None = None,
) -> str:
    lines = [
        "You are a LinkedIn feed classifier. Classify each post into exactly one category.",
        "",
        "## Categories",
    ]
    for cat in categories:
        lines.append(f"- **{cat['name']}**: {cat['description']}")

    wl = whitelist or {}
    bl = blacklist or {}
    has_wl = any(wl.get(k) for k in ("keywords", "authors"))
    has_bl = any(bl.get(k) for k in ("keywords", "authors"))

    if has_wl or has_bl:
        lines.append("")
        lines.append("## Override Rules")
        if has_wl:
            lines.append("Always classify as **Read** if:")
            if wl.get("keywords"):
                lines.append(f"- Post text contains any of: {wl['keywords']}")
            if wl.get("authors"):
                lines.append(f"- Author is any of: {wl['authors']}")
        if has_bl:
            lines.append("Always classify as **Skip** if:")
            if bl.get("keywords"):
                lines.append(f"- Post text contains any of: {bl['keywords']}")
            if bl.get("authors"):
                lines.append(f"- Author is any of: {bl['authors']}")
        lines.append("If both whitelist and blacklist match, classify as **Read**.")

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
    lines.append("## Instructions")
    lines.append("For each post, provide: category, confidence (0.0-1.0), and reasoning.")
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
    text_lower = post.post_text.lower()
    author_lower = post.author_name.lower()
    if any(kw.lower() in text_lower for kw in rule.get("keywords", [])):
        return True
    return any(a.lower() in author_lower for a in rule.get("authors", []))


def check_whitelist(post: Post, whitelist: dict) -> bool:
    """Return True if the post matches any whitelist condition."""
    return _matches(post, whitelist)


def check_blacklist(post: Post, blacklist: dict) -> bool:
    """Return True if the post matches any blacklist condition."""
    return _matches(post, blacklist)
