from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

from noise_cancel.models import Post
from noise_cancel.scraper.base import AbstractScraper

if TYPE_CHECKING:
    from noise_cancel.config import AppConfig

_LINKEDIN_LOGIN_URL = "https://www.linkedin.com/login"
_LINKEDIN_FEED_GLOB = "https://www.linkedin.com/feed**"
_LOGIN_TIMEOUT_MS = 300_000  # 5 minutes


class LinkedInScraper(AbstractScraper):
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._storage_state: dict | None = None

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
        return []

    async def close(self) -> None:
        pass

    def parse_post_element(self, raw: dict) -> Post:
        return Post(
            id=raw["id"],
            author_name=raw["author_name"],
            author_url=raw.get("author_url"),
            post_url=raw.get("post_url"),
            post_text=raw["post_text"],
            media_type=raw.get("media_type"),
            likes_count=raw.get("likes_count", 0),
            comments_count=raw.get("comments_count", 0),
            shares_count=raw.get("shares_count", 0),
            post_timestamp=raw.get("post_timestamp"),
        )
