from __future__ import annotations

import asyncio
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from noise_cancel.models import Post
from noise_cancel.scraper.anti_detection import human_scroll_sequence, random_delay, random_viewport
from noise_cancel.scraper.auth import (
    session_age_days as get_session_age_days,
)
from noise_cancel.scraper.auth import (
    session_expires_in_days as get_session_expires_in_days,
)
from noise_cancel.scraper.auth import (
    validate_session,
)
from noise_cancel.scraper.base import AbstractScraper

if TYPE_CHECKING:
    from noise_cancel.config import AppConfig

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


class LinkedInScraper(AbstractScraper):
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._storage_state: dict | None = None
        self._playwright: object | None = None

    def load_storage_state(self, state: dict) -> None:
        """Set storage state from a previously saved session dict."""
        self._storage_state = state

    def _session_paths(self) -> tuple[Path, Path]:
        data_dir = Path(self.config.general["data_dir"])
        key_path = data_dir / _LINKEDIN_SESSION_KEY_FILE
        session_path = data_dir / _LINKEDIN_SESSION_FILE
        return key_path, session_path

    def _session_ttl_days(self) -> int:
        platforms = self.config.scraper.get("platforms", {})
        linkedin_platform: dict[str, Any] = {}
        if isinstance(platforms, dict):
            maybe_linkedin = platforms.get("linkedin", {})
            if isinstance(maybe_linkedin, dict):
                linkedin_platform = maybe_linkedin

        ttl_value = linkedin_platform.get("session_ttl_days", self.config.scraper.get("session_ttl_days", 7))
        try:
            return int(ttl_value)
        except (TypeError, ValueError):
            return 7

    def session_age_days(self) -> float | None:
        _, session_path = self._session_paths()
        return get_session_age_days(str(session_path))

    def session_expires_in_days(self) -> float | None:
        _, session_path = self._session_paths()
        return get_session_expires_in_days(str(session_path), ttl_days=self._session_ttl_days())

    async def login(self, headed: bool = True) -> None:
        """Open browser for manual LinkedIn login. Stores session cookies internally."""
        pw = import_module("playwright.async_api")
        playwright = await pw.async_playwright().start()
        try:
            browser = await playwright.chromium.launch(headless=not headed)
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto(_LINKEDIN_LOGIN_URL)
            await page.wait_for_url(_LINKEDIN_FEED_GLOB, timeout=_LOGIN_TIMEOUT_MS)
            self._storage_state = dict(await context.storage_state())
            await browser.close()
        finally:
            await playwright.stop()

    @property
    def storage_state(self) -> dict | None:
        """Return captured storage state from the last login, or None."""
        return self._storage_state

    async def scrape_feed(self, scroll_count: int = 10) -> list[Post]:
        """Scrape LinkedIn feed posts by scrolling and extracting from the DOM."""
        if self._storage_state is None:
            key_path, session_path = self._session_paths()
            self._storage_state = validate_session(
                key_path=str(key_path),
                session_path=str(session_path),
                ttl_days=self._session_ttl_days(),
            )

        pw = import_module("playwright.async_api")
        playwright = await pw.async_playwright().start()
        self._playwright = playwright
        try:
            headless = self.config.scraper.get("headless", True)
            browser = await playwright.chromium.launch(headless=headless)
            context = await browser.new_context(
                storage_state=cast(Any, self._storage_state),
                viewport=cast(Any, random_viewport()),
            )
            page = await context.new_page()
            await page.goto(_LINKEDIN_FEED_URL, wait_until="domcontentloaded")

            # Verify we weren't redirected to login
            current_url = page.url
            if "/login" in current_url or "/checkpoint" in current_url:
                await browser.close()
                msg = f"Session expired or invalid — redirected to {current_url}"
                raise RuntimeError(msg)

            # Scroll the feed to load posts
            scroll_actions = human_scroll_sequence(scroll_count)
            for action in scroll_actions:
                delta_y = action["scroll_y"]
                if action["direction"] == "up":
                    delta_y = -delta_y
                await page.mouse.wheel(0, delta_y)
                await asyncio.sleep(action["delay"])

            # Extra pause to let final content load
            await asyncio.sleep(random_delay(1.0, 2.0))

            # Extract posts from the DOM
            raw_posts: list[dict] = await page.evaluate(_JS_EXTRACT_POSTS)

            await browser.close()
        finally:
            await playwright.stop()
            self._playwright = None

        # Parse and deduplicate
        seen_ids: set[str] = set()
        posts: list[Post] = []
        for raw in raw_posts:
            if not raw.get("post_text"):
                continue
            if not raw.get("id"):
                continue
            if raw["id"] in seen_ids:
                continue
            seen_ids.add(raw["id"])
            posts.append(self.parse_post_element(raw))
        return posts

    async def close(self) -> None:
        """Stop Playwright instance if running."""
        if self._playwright is not None:
            await self._playwright.stop()  # type: ignore[union-attr]
            self._playwright = None

    def parse_post_element(self, raw: dict) -> Post:
        return Post(
            id=raw["id"],
            author_name=raw["author_name"],
            author_url=raw.get("author_url"),
            post_url=raw.get("post_url"),
            post_text=raw["post_text"],
            media_type=raw.get("media_type"),
            post_timestamp=raw.get("post_timestamp"),
        )
