from __future__ import annotations

from noise_cancel.models import Classification, Post

_BUTTON_LABELS: dict[str, dict[str, str]] = {
    "english": {
        "view_on_linkedin": "View on LinkedIn",
    },
    "korean": {
        "view_on_linkedin": "LinkedIn에서 보기",
    },
}


def _get_labels(language: str) -> dict[str, str]:
    return _BUTTON_LABELS.get(language, _BUTTON_LABELS["english"])


def build_post_blocks(
    post: Post,
    classification: Classification,
    language: str = "english",
) -> list[dict]:
    """Build Slack Block Kit blocks for a single classified post."""
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

    # Actions block — View on LinkedIn button only
    if post.post_url:
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": labels["view_on_linkedin"], "emoji": True},
                    "url": post.post_url,
                },
            ],
        })

    return blocks


def build_digest_blocks(digest_text: str) -> list[dict]:
    """Build Slack Block Kit blocks for a daily digest payload."""
    sections = [section.strip() for section in digest_text.split("\n\n") if section.strip()]
    if not sections:
        sections = ["No digest content available."]

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "NoiseCancel Daily Digest", "emoji": True},
        }
    ]

    for section in sections:
        blocks.append({"type": "divider"})
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": section}})

    return blocks
