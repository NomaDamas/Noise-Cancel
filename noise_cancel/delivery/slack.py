from __future__ import annotations

import os

import httpx

from noise_cancel.config import AppConfig
from noise_cancel.delivery.blocks import build_post_blocks
from noise_cancel.models import Classification, Post


def send_to_slack(webhook_url: str, blocks: list[dict], text: str = "") -> bool:
    """Send blocks to Slack via incoming webhook. Return True on success."""
    payload: dict = {"blocks": blocks}
    if text:
        payload["text"] = text

    try:
        response = httpx.post(webhook_url, json=payload)
    except httpx.HTTPError:
        return False
    else:
        return response.status_code == 200


def deliver_posts(
    posts_with_classifications: list[tuple[Post, Classification]],
    config: AppConfig,
) -> int:
    """Deliver classified posts to Slack. Return count of successfully delivered."""
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        return 0

    slack_config = config.delivery.get("slack", {})
    include_categories = slack_config.get("include_categories", [])
    language = config.general.get("language", "english")

    delivered = 0
    for post, classification in posts_with_classifications:
        if classification.category not in include_categories:
            continue

        blocks = build_post_blocks(post, classification, language=language)
        fallback_text = f"[{classification.category}] {post.author_name}: {post.post_text[:100]}"

        if send_to_slack(webhook_url, blocks, text=fallback_text):
            delivered += 1

    return delivered
