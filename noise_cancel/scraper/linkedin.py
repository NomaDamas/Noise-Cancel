from __future__ import annotations

from typing import ClassVar

from noise_cancel.models import Post
from noise_cancel.scraper.playwright_base import PlaywrightScraper

_LINKEDIN_LOGIN_URL = "https://www.linkedin.com/login"
_LINKEDIN_FEED_URL = "https://www.linkedin.com/feed"
_LINKEDIN_FEED_GLOB = "https://www.linkedin.com/feed**"
_LOGIN_TIMEOUT_MS = 300_000  # 5 minutes
_LINKEDIN_SESSION_FILE = "session.enc"
_LINKEDIN_SESSION_KEY_FILE = "session.key"

# JavaScript to extract post data from the LinkedIn feed DOM.
# Selects activity elements and extracts key fields.
_JS_EXTRACT_POSTS = """
() => {
    const posts = [];
    const elements = document.querySelectorAll('div[data-urn^="urn:li:activity"]');
    for (const el of elements) {
        const urn = el.getAttribute('data-urn') || '';

        // Try multiple selectors for author name (LinkedIn DOM changes frequently)
        const authorEl =
            el.querySelector('.update-components-actor__name .visually-hidden') ||
            el.querySelector('.update-components-actor__title .visually-hidden') ||
            el.querySelector('.update-components-actor__name span[aria-hidden="true"]') ||
            el.querySelector('.update-components-actor__name');
        const authorLinkEl = el.querySelector('a.update-components-actor__meta-link');
        const textEl = el.querySelector('.update-components-text .break-words');

        const authorName = authorEl ? authorEl.textContent.trim() : '';
        const authorUrl = authorLinkEl ? authorLinkEl.href : '';
        const postText = textEl ? textEl.innerText.trim() : '';
        const postUrl = urn
            ? 'https://www.linkedin.com/feed/update/' + urn
            : '';

        posts.push({
            id: urn,
            author_name: authorName,
            author_url: authorUrl || null,
            post_url: postUrl || null,
            post_text: postText,
        });
    }
    return posts;
}
"""


class LinkedInScraper(PlaywrightScraper):
    platform_name = "linkedin"
    _login_url = _LINKEDIN_LOGIN_URL
    _home_url = _LINKEDIN_FEED_URL
    _home_glob = _LINKEDIN_FEED_GLOB
    _login_timeout_ms = _LOGIN_TIMEOUT_MS
    _session_file = _LINKEDIN_SESSION_FILE
    _session_key_file = _LINKEDIN_SESSION_KEY_FILE
    _js_extract_posts = _JS_EXTRACT_POSTS
    _invalid_url_indicators: ClassVar[list[str]] = ["/login", "/checkpoint"]

    def _parse_raw_post(self, raw: dict) -> Post:
        return Post(
            id=raw["id"],
            author_name=raw["author_name"],
            author_url=raw.get("author_url"),
            post_url=raw.get("post_url"),
            post_text=raw["post_text"],
            media_type=raw.get("media_type"),
            post_timestamp=raw.get("post_timestamp"),
        )

    # Keep backward-compatible alias
    parse_post_element = _parse_raw_post
