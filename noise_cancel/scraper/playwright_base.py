from __future__ import annotations

import asyncio
from abc import abstractmethod
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, cast

from noise_cancel.models import Post
from noise_cancel.scraper.anti_detection import human_scroll_sequence, random_delay, random_viewport
from noise_cancel.scraper.auth import (
    generate_key,
    save_session,
    validate_session,
)
from noise_cancel.scraper.auth import (
    session_age_days as get_session_age_days,
)
from noise_cancel.scraper.auth import (
    session_expires_in_days as get_session_expires_in_days,
)
from noise_cancel.scraper.base import AbstractScraper

if TYPE_CHECKING:
    from noise_cancel.config import AppConfig


class PlaywrightScraper(AbstractScraper):
    """Intermediate base for all Playwright-based scrapers.

    Subclasses must define:
    - platform_name: str class attribute (e.g. "linkedin", "x", "threads")
    - _login_url: str  -- URL to navigate to for login
    - _home_url: str   -- URL to navigate to for scraping the feed
    - _home_glob: str  -- glob pattern to wait for after login
    - _login_timeout_ms: int -- timeout for login wait
    - _session_file: str -- encrypted session filename
    - _session_key_file: str -- session key filename
    - _js_extract_posts: str -- JavaScript code to extract posts from the DOM
    - _parse_raw_post(raw: dict) -> Post
    - _invalid_url_indicators: list of URL substrings indicating failed auth redirect
    """

    # -- Subclass constants (must be overridden) --
    platform_name: str
    _login_url: str
    _home_url: str
    _home_glob: str
    _login_timeout_ms: int = 300_000
    _session_file: str
    _session_key_file: str
    _js_extract_posts: str
    _invalid_url_indicators: ClassVar[list[str]]

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._storage_state: dict | None = None
        self._playwright: object | None = None

    @property
    def storage_state(self) -> dict | None:
        """Return captured storage state from the last login, or None."""
        return self._storage_state

    def load_storage_state(self, state: dict) -> None:
        """Set storage state from a previously saved session dict."""
        self._storage_state = state

    def _session_paths(self) -> tuple[Path, Path]:
        data_dir = Path(self.config.general["data_dir"])
        key_path = data_dir / self._session_key_file
        session_path = data_dir / self._session_file
        return key_path, session_path

    def _session_ttl_days(self) -> int:
        platforms = self.config.scraper.get("platforms", {})
        platform_cfg: dict[str, Any] = {}
        if isinstance(platforms, dict):
            maybe_platform = platforms.get(self.platform_name, {})
            if isinstance(maybe_platform, dict):
                platform_cfg = maybe_platform

        ttl_value = platform_cfg.get("session_ttl_days", self.config.scraper.get("session_ttl_days", 7))
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
        """Open browser for manual login. Stores session cookies internally."""
        pw = import_module("playwright.async_api")
        playwright = await pw.async_playwright().start()
        try:
            browser = await playwright.chromium.launch(headless=not headed)
            try:
                context = await browser.new_context(viewport=cast(Any, random_viewport()))
                page = await context.new_page()
                await page.goto(self._login_url, wait_until="domcontentloaded")
                await page.wait_for_url(self._home_glob, timeout=self._login_timeout_ms)

                await self._post_login_validate(page)

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

    async def _post_login_validate(self, page: object) -> None:
        """Hook for subclasses to add post-login validation. Default is no-op."""

    async def scrape_feed(self, scroll_count: int = 10) -> list[Post]:
        """Scrape feed posts by scrolling and extracting from the DOM."""
        key_path, session_path = self._session_paths()
        session_data = validate_session(
            key_path=str(key_path),
            session_path=str(session_path),
            ttl_days=self._session_ttl_days(),
        )
        self._storage_state = session_data

        pw = import_module("playwright.async_api")
        playwright = await pw.async_playwright().start()
        self._playwright = playwright
        try:
            headless = bool(self.config.scraper.get("headless", True))
            browser = await playwright.chromium.launch(headless=headless)
            try:
                context = await browser.new_context(
                    storage_state=cast(Any, session_data),
                    viewport=cast(Any, random_viewport()),
                )
                page = await context.new_page()
                await page.goto(self._home_url, wait_until="domcontentloaded")

                current_url = page.url
                for indicator in self._invalid_url_indicators:
                    if indicator in current_url:
                        msg = f"Session expired or invalid — redirected to {current_url}"
                        raise RuntimeError(msg)

                scroll_actions = human_scroll_sequence(scroll_count)
                for action in scroll_actions:
                    delta_y = action["scroll_y"]
                    if action["direction"] == "up":
                        delta_y = -delta_y
                    await page.mouse.wheel(0, delta_y)
                    await asyncio.sleep(action["delay"])

                await asyncio.sleep(random_delay(1.0, 2.0))
                raw_posts: list[dict] = await page.evaluate(self._js_extract_posts)
            finally:
                await browser.close()
        finally:
            await playwright.stop()
            self._playwright = None

        return self._deduplicate_posts(raw_posts)

    def _deduplicate_posts(self, raw_posts: list[dict]) -> list[Post]:
        """Filter empty text/id and deduplicate by post id."""
        seen_ids: set[str] = set()
        posts: list[Post] = []
        for raw in raw_posts:
            post = self._parse_raw_post(raw)
            if not post.post_text:
                continue
            if not post.id:
                continue
            if post.id in seen_ids:
                continue
            seen_ids.add(post.id)
            posts.append(post)
        return posts

    @abstractmethod
    def _parse_raw_post(self, raw: dict) -> Post:
        """Parse a raw dict from JS extraction into a Post model."""
        ...

    async def close(self) -> None:
        """Stop Playwright instance if running."""
        if self._playwright is not None:
            await self._playwright.stop()  # type: ignore[union-attr]
            self._playwright = None
