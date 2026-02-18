from __future__ import annotations

from noise_cancel.models import Classification, Post

# Category -> emoji mapping (Slack emoji shortcodes)
_CATEGORY_EMOJIS: dict[str, str] = {
    "Must Read": ":fire:",
    "Interesting": ":eyes:",
    "Noise": ":mute:",
    "Spam": ":no_entry:",
}


def build_post_blocks(post: Post, classification: Classification, config: dict) -> list[dict]:
    """Build Slack Block Kit blocks for a single classified post."""
    max_preview = config.get("max_text_preview", 300)
    include_reasoning = config.get("include_reasoning", True)
    enable_feedback = config.get("enable_feedback_buttons", True)

    emoji = _CATEGORY_EMOJIS.get(classification.category, ":question:")
    blocks: list[dict] = []

    # Header with category emoji + name
    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": f"{emoji} {classification.category}",
            "emoji": True,
        },
    })

    # Author section
    author_text = f"*<{post.author_url}|{post.author_name}>*" if post.author_url else f"*{post.author_name}*"

    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": author_text},
    })

    # Post text preview (truncated)
    preview = post.post_text
    if len(preview) > max_preview:
        preview = preview[:max_preview] + "..."

    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": preview},
    })

    # Context block with confidence and optional reasoning
    confidence_pct = int(classification.confidence * 100)
    context_elements: list[dict] = [
        {"type": "mrkdwn", "text": f"*Confidence:* {confidence_pct}%"},
    ]
    if include_reasoning:
        context_elements.append({"type": "mrkdwn", "text": f"*Reasoning:* {classification.reasoning}"})

    blocks.append({
        "type": "context",
        "elements": context_elements,
    })

    # Actions block
    action_elements: list[dict] = []

    if enable_feedback:
        action_elements.extend([
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "\ud83d\udc4d Useful", "emoji": True},
                "value": f"useful|{post.id}",
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "\ud83d\udc4e Not Useful", "emoji": True},
                "value": f"not_useful|{post.id}",
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "\ud83d\udd07 Mute Similar", "emoji": True},
                "value": f"mute_similar|{post.id}",
            },
        ])

    if post.post_url:
        action_elements.append({
            "type": "button",
            "text": {"type": "plain_text", "text": "View on LinkedIn", "emoji": True},
            "url": post.post_url,
        })

    if action_elements:
        blocks.append({
            "type": "actions",
            "elements": action_elements,
        })

    return blocks
