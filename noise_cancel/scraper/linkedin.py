from __future__ import annotations

from noise_cancel.config import AppConfig
from noise_cancel.models import Post
from noise_cancel.scraper.base import AbstractScraper


class LinkedInScraper(AbstractScraper):
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._headed: bool = True

    async def login(self, headed: bool = True) -> None:
        self._headed = headed

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
