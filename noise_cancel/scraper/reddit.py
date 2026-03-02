from __future__ import annotations

import os
from datetime import datetime, timezone
from importlib import import_module
from typing import TYPE_CHECKING, Any

from noise_cancel.models import Post
from noise_cancel.scraper.base import AbstractScraper

if TYPE_CHECKING:
    import praw

    from noise_cancel.config import AppConfig

_DEFAULT_USER_AGENT = "noise-cancel/0.0.1"

_CREDENTIAL_ENV_MAP = {
    "client_id": ("NC_REDDIT_CLIENT_ID", "REDDIT_CLIENT_ID"),
    "client_secret": ("NC_REDDIT_CLIENT_SECRET", "REDDIT_CLIENT_SECRET"),
    "username": ("NC_REDDIT_USERNAME", "REDDIT_USERNAME"),
    "password": ("NC_REDDIT_PASSWORD", "REDDIT_PASSWORD"),
}


class RedditScraper(AbstractScraper):
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._reddit: praw.Reddit | None = None

    @property
    def reddit(self) -> praw.Reddit | None:
        return self._reddit

    def _platform_config(self) -> dict[str, Any]:
        platforms = self.config.scraper.get("platforms", {})
        if not isinstance(platforms, dict):
            return {}

        maybe_reddit = platforms.get("reddit", {})
        if isinstance(maybe_reddit, dict):
            return maybe_reddit
        return {}

    def _resolve_config_value(self, value: object, *, fallback_env: tuple[str, str]) -> str:
        if isinstance(value, str):
            raw = value.strip()
            if raw.startswith("${") and raw.endswith("}") and len(raw) > 3:
                return os.getenv(raw[2:-1], "")
            if raw.startswith("$") and len(raw) > 1:
                return os.getenv(raw[1:], "")
            if raw.startswith("env:") and len(raw) > 4:
                return os.getenv(raw[4:].strip(), "")
            if raw:
                return raw

        primary, secondary = fallback_env
        return os.getenv(primary, os.getenv(secondary, ""))

    def _credentials(self) -> dict[str, str]:
        platform_config = self._platform_config()
        return {
            key: self._resolve_config_value(platform_config.get(key), fallback_env=env_names)
            for key, env_names in _CREDENTIAL_ENV_MAP.items()
        }

    async def login(self, headed: bool = True) -> None:
        del headed  # OAuth via API does not require browser automation.

        credentials = self._credentials()
        missing = [key for key, value in credentials.items() if not value]
        if missing:
            msg = f"Missing Reddit credentials: {', '.join(missing)}"
            raise ValueError(msg)

        platform_config = self._platform_config()
        user_agent_raw = platform_config.get("user_agent", _DEFAULT_USER_AGENT)
        user_agent = (
            self._resolve_config_value(user_agent_raw, fallback_env=("NC_REDDIT_USER_AGENT", "REDDIT_USER_AGENT"))
            or f"{_DEFAULT_USER_AGENT} by {credentials['username']}"
        )

        praw = import_module("praw")
        reddit = praw.Reddit(
            client_id=credentials["client_id"],
            client_secret=credentials["client_secret"],
            username=credentials["username"],
            password=credentials["password"],
            user_agent=user_agent,
        )
        reddit.user.me()
        self._reddit = reddit

    async def scrape_feed(self, scroll_count: int = 10) -> list[Post]:
        if self._reddit is None:
            await self.login(headed=False)

        if self._reddit is None:
            msg = "Reddit client is not initialized"
            raise RuntimeError(msg)

        limit = max(1, int(scroll_count))
        feed_sort = str(self._platform_config().get("feed_sort", "best")).strip().lower()
        if feed_sort == "hot":
            submissions = self._reddit.front.hot(limit=limit)
        else:
            submissions = self._reddit.front.best(limit=limit)

        posts: list[Post] = []
        seen_ids: set[str] = set()
        for submission in submissions:
            post = self.parse_submission(submission)
            if not post.id or post.id in seen_ids:
                continue
            if not post.post_text:
                continue
            seen_ids.add(post.id)
            posts.append(post)
        return posts

    async def close(self) -> None:
        self._reddit = None

    def parse_submission(self, submission: object) -> Post:
        post_id = _clean_str(getattr(submission, "id", ""))
        author_name = _clean_str(getattr(getattr(submission, "author", None), "name", "")) or "[deleted]"
        title = _clean_str(getattr(submission, "title", ""))
        selftext = _clean_str(getattr(submission, "selftext", ""))
        post_text = title
        if selftext:
            post_text = f"{title}\n\n{selftext}" if title else selftext

        permalink = _clean_str(getattr(submission, "permalink", ""))
        post_url = None
        if permalink:
            post_url = f"https://reddit.com{permalink}" if permalink.startswith("/") else permalink
        if post_url is None:
            post_url = _optional_clean_str(getattr(submission, "url", None))

        created_utc = getattr(submission, "created_utc", None)
        post_timestamp = None
        if created_utc is not None:
            try:
                post_timestamp = datetime.fromtimestamp(float(created_utc), tz=timezone.utc).isoformat()
            except (TypeError, ValueError):
                post_timestamp = None

        subreddit = _clean_str(getattr(getattr(submission, "subreddit", None), "display_name", ""))
        author_url = None if author_name == "[deleted]" else f"https://reddit.com/user/{author_name}"

        metadata: dict[str, Any] = {}
        if subreddit:
            metadata["subreddit"] = subreddit

        return Post(
            id=post_id,
            platform="reddit",
            author_name=author_name,
            author_url=author_url,
            post_url=post_url,
            post_text=post_text,
            post_timestamp=post_timestamp,
            metadata=metadata,
        )


def _clean_str(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _optional_clean_str(value: object) -> str | None:
    cleaned = _clean_str(value)
    return cleaned or None
