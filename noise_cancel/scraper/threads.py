from __future__ import annotations

import re
from typing import ClassVar

from noise_cancel.models import Post
from noise_cancel.scraper.playwright_base import PlaywrightScraper
from noise_cancel.scraper.utils import clean_str, optional_clean_str

_THREADS_LOGIN_URL = "https://www.threads.net"
_THREADS_HOME_URL = "https://www.threads.net"
# TODO: This glob is broad and can match error pages. We add a post-login
# validation check (_post_login_validate) that verifies actual feed content
# is present before accepting the session. A tighter glob would be preferable
# but Threads does not expose a reliably distinct authenticated URL pattern.
_THREADS_HOME_GLOB = "https://www.threads.net/**"
_LOGIN_TIMEOUT_MS = 300_000  # 5 minutes
_THREADS_POST_ID_RE = re.compile(r"/post/([^/?#]+)")
_THREADS_SESSION_FILE = "threads_session.enc"
_THREADS_SESSION_KEY_FILE = "threads_session.key"

# JavaScript to extract post data from the Threads home feed DOM.
_JS_EXTRACT_POSTS = """
() => {
    const posts = [];
    const threadPosts = document.querySelectorAll('div[role="article"]');
    for (const post of threadPosts) {
        const authorEl =
            post.querySelector('a[href^="/@"] span') ||
            post.querySelector('header a[href^="/@"]') ||
            post.querySelector('h2 span');
        const textEl =
            post.querySelector('div[data-pressable-container="true"] span') ||
            post.querySelector('[data-testid="thread-post-text"]') ||
            post.querySelector('span[dir="auto"]');
        const timeEl = post.querySelector('time');
        const postLinkEl =
            post.querySelector('a[href*="/post/"]') ||
            (timeEl && timeEl.parentElement && timeEl.parentElement.tagName === 'A' ? timeEl.parentElement : null);

        const authorName = authorEl ? authorEl.innerText.trim() : '';
        const postText = textEl ? textEl.innerText.trim() : '';
        const postUrl = postLinkEl ? postLinkEl.href : '';
        const postTimestamp = timeEl ? timeEl.getAttribute('datetime') : null;
        const dataPostId = post.getAttribute('data-post-id') || '';

        posts.push({
            id: dataPostId,
            author_name: authorName,
            post_text: postText,
            post_url: postUrl || null,
            post_timestamp: postTimestamp,
        });
    }
    return posts;
}
"""


class ThreadsScraper(PlaywrightScraper):
    platform_name = "threads"
    _login_url = _THREADS_LOGIN_URL
    _home_url = _THREADS_HOME_URL
    _home_glob = _THREADS_HOME_GLOB
    _login_timeout_ms = _LOGIN_TIMEOUT_MS
    _session_file = _THREADS_SESSION_FILE
    _session_key_file = _THREADS_SESSION_KEY_FILE
    _js_extract_posts = _JS_EXTRACT_POSTS
    _invalid_url_indicators: ClassVar[list[str]] = ["/login", "/accounts/login"]

    async def _post_login_validate(self, page: object) -> None:
        """Verify the page actually has feed content after login.

        The home glob is broad (matches any threads.net path), so we check
        that feed article elements are present to confirm we are on an
        authenticated feed page rather than an error or login page.
        """
        # page is a Playwright Page object; use evaluate to check for feed content
        has_feed = await page.evaluate(  # type: ignore[union-attr]
            "() => document.querySelectorAll('div[role=\"article\"]').length > 0"
        )
        if not has_feed:
            # Also check for a profile avatar or navigation element as secondary signal
            has_nav = await page.evaluate(  # type: ignore[union-attr]
                "() => !!(document.querySelector('nav') || document.querySelector('[role=\"navigation\"]'))"
            )
            if not has_nav:
                msg = (
                    "Post-login validation failed: no feed content or navigation "
                    "found. The login may not have completed successfully."
                )
                raise RuntimeError(msg)

    def _parse_raw_post(self, raw: dict) -> Post:
        post_url = raw.get("post_url")
        post_id = clean_str(raw.get("id"))
        if not post_id and isinstance(post_url, str):
            match = _THREADS_POST_ID_RE.search(post_url)
            if match:
                post_id = match.group(1)

        return Post(
            id=post_id,
            platform="threads",
            author_name=clean_str(raw.get("author_name")),
            author_url=optional_clean_str(raw.get("author_url")),
            post_url=optional_clean_str(post_url),
            post_text=clean_str(raw.get("post_text")),
            media_type=optional_clean_str(raw.get("media_type")),
            post_timestamp=optional_clean_str(raw.get("post_timestamp")),
        )

    # Keep backward-compatible alias
    parse_post_element = _parse_raw_post
