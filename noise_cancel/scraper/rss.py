from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any

import feedparser
import httpx

from noise_cancel.models import Post
from noise_cancel.scraper.base import AbstractScraper
from noise_cancel.scraper.utils import clean_str, optional_clean_str

if TYPE_CHECKING:
    from noise_cancel.config import AppConfig

_DEFAULT_TIMEOUT_SECONDS = 10.0


class RssScraper(AbstractScraper):
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    async def login(self, headed: bool = True) -> None:
        del headed  # RSS feeds do not require authentication.

    async def scrape_feed(self, scroll_count: int = 10) -> list[Post]:
        del scroll_count  # RSS scraping is URL-based, not scroll-based.

        posts: list[Post] = []
        seen_ids: set[str] = set()
        feed_configs = self._feed_configs()
        if not feed_configs:
            return posts

        timeout_seconds = self._timeout_seconds()
        timeout = httpx.Timeout(timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            for feed in feed_configs:
                feed_url = feed["url"]
                feed_name = feed["name"]

                payload = await self._fetch_feed_payload(client, feed_url)
                if payload is None:
                    continue

                parsed = feedparser.parse(payload)
                entries = parsed.get("entries", [])
                if not isinstance(entries, list):
                    continue

                bozo = bool(parsed.get("bozo", False))
                if bozo and not entries:
                    continue

                parsed_feed = parsed.get("feed", {})
                parsed_feed_author = clean_str(_value(parsed_feed, "author"))

                for index, entry in enumerate(entries):
                    post = self.parse_entry(
                        entry,
                        feed_url=feed_url,
                        feed_name=feed_name,
                        feed_author=parsed_feed_author,
                        index=index,
                    )
                    if not post.post_text:
                        continue
                    if not post.id or post.id in seen_ids:
                        continue
                    seen_ids.add(post.id)
                    posts.append(post)
        return posts

    async def close(self) -> None:
        return None

    def _platform_config(self) -> dict[str, Any]:
        platforms = self.config.scraper.get("platforms", {})
        if not isinstance(platforms, dict):
            return {}

        maybe_rss = platforms.get("rss", {})
        if isinstance(maybe_rss, dict):
            return maybe_rss
        return {}

    def _feed_configs(self) -> list[dict[str, str]]:
        feeds = self._platform_config().get("feeds", [])
        if not isinstance(feeds, list):
            return []

        resolved: list[dict[str, str]] = []
        for feed in feeds:
            if not isinstance(feed, dict):
                continue
            url = clean_str(feed.get("url"))
            if not url:
                continue
            resolved.append({"url": url, "name": clean_str(feed.get("name"))})
        return resolved

    def _timeout_seconds(self) -> float:
        raw_timeout = self._platform_config().get("request_timeout_seconds", _DEFAULT_TIMEOUT_SECONDS)
        try:
            timeout_seconds = float(raw_timeout)
        except (TypeError, ValueError):
            return _DEFAULT_TIMEOUT_SECONDS
        return timeout_seconds if timeout_seconds > 0 else _DEFAULT_TIMEOUT_SECONDS

    async def _fetch_feed_payload(self, client: httpx.AsyncClient, url: str) -> bytes | None:
        try:
            response = await client.get(url)
            response.raise_for_status()
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.HTTPError):
            return None
        return response.content

    def parse_entry(
        self,
        entry: object,
        *,
        feed_url: str,
        feed_name: str,
        feed_author: str,
        index: int,
    ) -> Post:
        post_url = optional_clean_str(_value(entry, "link"))
        post_text = _extract_post_text(entry)
        author_name = optional_clean_str(_value(entry, "author")) or feed_author or feed_name or "Unknown RSS feed"
        post_id = (
            optional_clean_str(_value(entry, "id"))
            or optional_clean_str(_value(entry, "guid"))
            or post_url
            or _fallback_post_id(feed_url, index, post_text)
        )

        return Post(
            id=post_id,
            platform="rss",
            author_name=author_name,
            post_url=post_url,
            post_text=post_text,
            post_timestamp=optional_clean_str(_value(entry, "published"))
            or optional_clean_str(_value(entry, "updated")),
            metadata={
                "feed_name": feed_name or feed_url,
                "feed_url": feed_url,
            },
        )


def _extract_post_text(entry: object) -> str:
    summary = clean_str(_value(entry, "summary"))
    if summary:
        return summary

    content = _value(entry, "content")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict):
                for key, value in item.items():
                    if key == "value":
                        text_value = clean_str(value)
                        if text_value:
                            return text_value

    return clean_str(_value(entry, "description"))


def _fallback_post_id(feed_url: str, index: int, post_text: str) -> str:
    base = f"{feed_url}|{index}|{post_text}".encode()
    return hashlib.sha256(base).hexdigest()


def _value(data: object, field: str) -> object:
    if isinstance(data, dict):
        for key, value in data.items():
            if key == field:
                return value
        return None
    return getattr(data, field, None)
