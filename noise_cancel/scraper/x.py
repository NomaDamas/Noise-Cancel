from __future__ import annotations

import re
from typing import ClassVar

from noise_cancel.models import Post
from noise_cancel.scraper.playwright_base import PlaywrightScraper
from noise_cancel.scraper.utils import clean_str, optional_clean_str

_X_LOGIN_URL = "https://x.com"
_X_HOME_URL = "https://x.com/home"
_X_HOME_GLOB = "https://x.com/home**"
_LOGIN_TIMEOUT_MS = 300_000  # 5 minutes
_STATUS_ID_RE = re.compile(r"/status/(\d+)")
_X_SESSION_FILE = "x_session.enc"
_X_SESSION_KEY_FILE = "x_session.key"

# JavaScript to extract tweet data from X home timeline DOM.
_JS_EXTRACT_POSTS = """
() => {
    const posts = [];
    const tweets = document.querySelectorAll('article[data-testid="tweet"]');
    for (const tweet of tweets) {
        const userEl = tweet.querySelector('div[data-testid="User-Name"]');
        const textEl = tweet.querySelector('div[data-testid="tweetText"]');
        const timeEl = tweet.querySelector('time');
        const statusLinkEl = timeEl && timeEl.parentElement && timeEl.parentElement.tagName === 'A'
            ? timeEl.parentElement
            : tweet.querySelector('a[href*="/status/"]');

        const authorName = userEl ? userEl.innerText.split('\\n')[0].trim() : '';
        const postText = textEl ? textEl.innerText.trim() : '';
        const postUrl = statusLinkEl ? statusLinkEl.href : '';
        const postTimestamp = timeEl ? timeEl.getAttribute('datetime') : null;
        const dataTweetId = tweet.getAttribute('data-tweet-id') || '';

        posts.push({
            id: dataTweetId,
            author_name: authorName,
            post_text: postText,
            post_url: postUrl || null,
            post_timestamp: postTimestamp,
        });
    }
    return posts;
}
"""


class XScraper(PlaywrightScraper):
    platform_name = "x"
    _login_url = _X_LOGIN_URL
    _home_url = _X_HOME_URL
    _home_glob = _X_HOME_GLOB
    _login_timeout_ms = _LOGIN_TIMEOUT_MS
    _session_file = _X_SESSION_FILE
    _session_key_file = _X_SESSION_KEY_FILE
    _js_extract_posts = _JS_EXTRACT_POSTS
    _invalid_url_indicators: ClassVar[list[str]] = ["/login", "/i/flow"]

    def _parse_raw_post(self, raw: dict) -> Post:
        post_url = raw.get("post_url")
        post_id = clean_str(raw.get("id"))
        if not post_id and isinstance(post_url, str):
            match = _STATUS_ID_RE.search(post_url)
            if match:
                post_id = match.group(1)

        return Post(
            id=post_id,
            platform="x",
            author_name=clean_str(raw.get("author_name")),
            author_url=optional_clean_str(raw.get("author_url")),
            post_url=optional_clean_str(post_url),
            post_text=clean_str(raw.get("post_text")),
            media_type=optional_clean_str(raw.get("media_type")),
            post_timestamp=optional_clean_str(raw.get("post_timestamp")),
        )

    # Keep backward-compatible alias
    parse_post_element = _parse_raw_post
