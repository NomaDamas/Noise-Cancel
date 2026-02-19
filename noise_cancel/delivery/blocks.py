from __future__ import annotations

import emoji as emoji_lib

from noise_cancel.models import Classification, Post

_BUTTON_LABELS: dict[str, dict[str, str]] = {
    "english": {
        "useful": ":thumbsup: Useful",
        "not_useful": ":thumbsdown: Not Useful",
        "mute_similar": ":muted_speaker: Mute Similar",
        "view_on_linkedin": "View on LinkedIn",
    },
    "korean": {
        "useful": ":thumbsup: 유용해요",
        "not_useful": ":thumbsdown: 별로예요",
        "mute_similar": ":muted_speaker: 비슷한 글 숨기기",
        "view_on_linkedin": "LinkedIn에서 보기",
    },
}


def _get_labels(language: str) -> dict[str, str]:
    return _BUTTON_LABELS.get(language, _BUTTON_LABELS["english"])


def _emojize(text: str) -> str:
    """Convert emoji shortcodes to proper Unicode characters."""
    return emoji_lib.emojize(text, language="alias")


def build_post_blocks(
    post: Post,
    classification: Classification,
    config: dict,
    language: str = "english",
) -> list[dict]:
    """Build Slack Block Kit blocks for a single classified post."""
    enable_feedback = config.get("enable_feedback_buttons", True)
    labels = _get_labels(language)

    blocks: list[dict] = []

    # Author name (plain text, no profile link)
    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": f"*{post.author_name}*"},
    })

    # Summary (fall back to truncated post text if no summary)
    summary_text = classification.summary or post.post_text[:300]
    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": summary_text},
    })

    # Actions block
    action_elements: list[dict] = []

    if enable_feedback:
        action_elements.extend([
            {
                "type": "button",
                "text": {"type": "plain_text", "text": _emojize(labels["useful"]), "emoji": True},
                "value": f"useful|{post.id}",
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": _emojize(labels["not_useful"]), "emoji": True},
                "value": f"not_useful|{post.id}",
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": _emojize(labels["mute_similar"]), "emoji": True},
                "value": f"mute_similar|{post.id}",
            },
        ])

    if post.post_url:
        action_elements.append({
            "type": "button",
            "text": {"type": "plain_text", "text": labels["view_on_linkedin"], "emoji": True},
            "url": post.post_url,
        })

    if action_elements:
        blocks.append({
            "type": "actions",
            "elements": action_elements,
        })

    return blocks
