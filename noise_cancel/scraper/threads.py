from __future__ import annotations

import asyncio
import re
from importlib import import_module
from typing import Any, ClassVar, cast

from noise_cancel.models import Post
from noise_cancel.scraper.auth import generate_key, save_session
from noise_cancel.scraper.playwright_base import PlaywrightScraper, random_viewport
from noise_cancel.scraper.utils import clean_str, optional_clean_str

_THREADS_LOGIN_URL = "https://www.threads.com/login"
_THREADS_HOME_URL = "https://www.threads.com"
_THREADS_HOME_GLOB = "https://www.threads.com/**"
_LOGIN_TIMEOUT_MS = 300_000  # 5 minutes
_LOGIN_POLL_INTERVAL_S = 2.0  # poll for feed content every N seconds
_THREADS_POST_ID_RE = re.compile(r"/post/([^/?#]+)")
_THREADS_SESSION_FILE = "threads_session.enc"
_THREADS_SESSION_KEY_FILE = "threads_session.key"

# JavaScript to extract post data from the Threads home feed DOM.
# Threads (as of 2026-03) uses [data-pressable-container="true"] for post
# containers and a[href*="/@"] links for author/post identification.
# There are no role="article" or <article> elements in the current DOM.
_JS_EXTRACT_POSTS = """
() => {
    const posts = [];
    const seen = new Set();

    // Find all post links (/@username/post/ID pattern)
    const postLinks = document.querySelectorAll('a[href*="/post/"]');
    for (const link of postLinks) {
        const href = link.href || '';
        const match = href.match(/\\/@([^/]+)\\/post\\/([^/?#]+)/);
        if (!match) continue;

        const authorHandle = match[1];
        const postId = match[2];
        if (seen.has(postId)) continue;
        seen.add(postId);

        // Walk up to find the pressable container (post boundary)
        let container = link;
        for (let i = 0; i < 15; i++) {
            if (!container.parentElement) break;
            container = container.parentElement;
            if (container.getAttribute('data-pressable-container') === 'true') break;
        }

        // Extract author display name from /@username link's text
        const authorLinkEl = container.querySelector('a[href*="/@' + authorHandle + '"] span');
        const authorName = authorLinkEl ? authorLinkEl.innerText.trim() : authorHandle;

        // Extract post text: collect all span[dir="auto"] within container
        const textSpans = container.querySelectorAll('span[dir="auto"]');
        let postText = '';
        for (const span of textSpans) {
            const t = span.innerText.trim();
            // Skip if it looks like just the author name or a UI label
            if (t === authorName || t.length < 2) continue;
            if (postText) postText += '\\n';
            postText += t;
        }

        // Extract timestamp
        const timeEl = container.querySelector('time');
        const postTimestamp = timeEl ? timeEl.getAttribute('datetime') : null;

        posts.push({
            id: postId,
            author_name: authorName,
            post_text: postText,
            post_url: href,
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
    _invalid_url_indicators: ClassVar[list[str]] = ["/login", "/accounts/login", "/accounts"]

    async def login(self, headed: bool = True) -> None:
        """Override login to poll for authenticated feed content.

        Threads keeps the same URL before and after login, so wait_for_url
        cannot detect login completion. Instead, we navigate to the login page
        and poll the DOM for feed content (articles or navigation elements)
        that only appear when authenticated.
        """
        pw = import_module("playwright.async_api")
        playwright = await pw.async_playwright().start()
        try:
            browser = await playwright.chromium.launch(headless=not headed)
            try:
                context = await browser.new_context(viewport=cast(Any, random_viewport()))
                page = await context.new_page()
                await page.goto(self._login_url, wait_until="domcontentloaded")

                # Poll until authenticated feed content appears or timeout.
                # After login, Threads redirects to the home feed where
                # role="region" and role="menu" elements appear.
                # page.evaluate() can throw during navigations (e.g. Instagram
                # OAuth redirect), so we catch and retry on those errors.
                deadline = asyncio.get_event_loop().time() + (self._login_timeout_ms / 1000)
                authenticated = False
                while asyncio.get_event_loop().time() < deadline:
                    try:
                        current_url = page.url
                        # Skip checks while still on login/accounts pages
                        if "/login" in current_url or "/accounts" in current_url:
                            await asyncio.sleep(_LOGIN_POLL_INTERVAL_S)
                            continue
                        # Check for feed indicators: region + menu roles appear
                        # on the authenticated home feed but not on login pages
                        has_feed_indicators = await page.evaluate(
                            "() => !!(document.querySelector('[role=\"region\"]')"
                            " && document.querySelector('[role=\"menu\"]'))"
                        )
                        if has_feed_indicators:
                            authenticated = True
                            break
                    except Exception:  # noqa: S110 — expected during page navigations
                        pass
                    await asyncio.sleep(_LOGIN_POLL_INTERVAL_S)

                if not authenticated:
                    msg = "Login timed out: no feed content detected after authentication."
                    raise RuntimeError(msg)

                self._storage_state = dict(await context.storage_state())

                key_path, session_path = self._session_paths()
                key_path.parent.mkdir(parents=True, exist_ok=True)
                if key_path.exists():
                    key = key_path.read_text().strip()
                else:
                    key = generate_key()
                    key_path.write_text(key)
                    key_path.chmod(0o600)

                save_session(self._storage_state, key, str(session_path))
                session_path.chmod(0o600)
            finally:
                await browser.close()
        finally:
            await playwright.stop()

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
