from __future__ import annotations

import asyncio
import re
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

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

_THREADS_LOGIN_URL = "https://www.threads.net"
_THREADS_HOME_URL = "https://www.threads.net"
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


class ThreadsScraper(AbstractScraper):
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._storage_state: dict | None = None
        self._playwright: object | None = None

    @property
    def storage_state(self) -> dict | None:
        return self._storage_state

    def load_storage_state(self, state: dict) -> None:
        self._storage_state = state

    def _session_paths(self) -> tuple[Path, Path]:
        data_dir = Path(self.config.general["data_dir"])
        key_path = data_dir / _THREADS_SESSION_KEY_FILE
        session_path = data_dir / _THREADS_SESSION_FILE
        return key_path, session_path

    def _session_ttl_days(self) -> int:
        platforms = self.config.scraper.get("platforms", {})
        threads_platform: dict[str, Any] = {}
        if isinstance(platforms, dict):
            maybe_threads = platforms.get("threads", {})
            if isinstance(maybe_threads, dict):
                threads_platform = maybe_threads

        ttl_value = threads_platform.get("session_ttl_days", self.config.scraper.get("session_ttl_days", 7))
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
        pw = import_module("playwright.async_api")
        playwright = await pw.async_playwright().start()
        try:
            browser = await playwright.chromium.launch(headless=not headed)
            try:
                context = await browser.new_context(viewport=cast(Any, random_viewport()))
                page = await context.new_page()
                await page.goto(_THREADS_LOGIN_URL, wait_until="domcontentloaded")
                await page.wait_for_url(_THREADS_HOME_GLOB, timeout=_LOGIN_TIMEOUT_MS)

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

    async def scrape_feed(self, scroll_count: int = 10) -> list[Post]:
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
                await page.goto(_THREADS_HOME_URL, wait_until="domcontentloaded")

                current_url = page.url
                if "/login" in current_url or "/accounts/login" in current_url:
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
                raw_posts: list[dict] = await page.evaluate(_JS_EXTRACT_POSTS)
            finally:
                await browser.close()
        finally:
            await playwright.stop()
            self._playwright = None

        seen_ids: set[str] = set()
        posts: list[Post] = []
        for raw in raw_posts:
            post = self.parse_post_element(raw)
            if not post.post_text:
                continue
            if not post.id:
                continue
            if post.id in seen_ids:
                continue
            seen_ids.add(post.id)
            posts.append(post)
        return posts

    async def close(self) -> None:
        if self._playwright is not None:
            await self._playwright.stop()  # type: ignore[union-attr]
            self._playwright = None

    def parse_post_element(self, raw: dict) -> Post:
        post_url = raw.get("post_url")
        post_id = _clean_str(raw.get("id"))
        if not post_id and isinstance(post_url, str):
            match = _THREADS_POST_ID_RE.search(post_url)
            if match:
                post_id = match.group(1)

        return Post(
            id=post_id,
            platform="threads",
            author_name=_clean_str(raw.get("author_name")),
            author_url=_optional_clean_str(raw.get("author_url")),
            post_url=_optional_clean_str(post_url),
            post_text=_clean_str(raw.get("post_text")),
            media_type=_optional_clean_str(raw.get("media_type")),
            post_timestamp=_optional_clean_str(raw.get("post_timestamp")),
        )


def _clean_str(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _optional_clean_str(value: object) -> str | None:
    cleaned = _clean_str(value)
    return cleaned or None
