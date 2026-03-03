from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from noise_cancel.models import Post


def _make_submission(
    *,
    post_id: str,
    author_name: str | None,
    title: str,
    selftext: str,
    permalink: str,
    url: str,
    subreddit: str,
    created_utc: float,
):
    author = SimpleNamespace(name=author_name) if author_name is not None else None
    return SimpleNamespace(
        id=post_id,
        author=author,
        title=title,
        selftext=selftext,
        permalink=permalink,
        url=url,
        subreddit=SimpleNamespace(display_name=subreddit),
        created_utc=created_utc,
    )


class TestRedditScraperLogin:
    @pytest.mark.anyio
    async def test_login_uses_config_credentials(self, app_config):
        from noise_cancel.scraper.reddit import RedditScraper

        app_config.scraper["platforms"]["reddit"] = {
            "enabled": True,
            "client_id": "client-id",
            "client_secret": "client-secret",
            "username": "reddit-user",
            "password": "reddit-pass",
        }
        scraper = RedditScraper(app_config)

        mock_reddit = MagicMock()
        mock_reddit.user.me.return_value = object()
        mock_praw = MagicMock()
        mock_praw.Reddit.return_value = mock_reddit

        with patch("noise_cancel.scraper.reddit.import_module", return_value=mock_praw):
            await scraper.login()

        kwargs = mock_praw.Reddit.call_args.kwargs
        assert kwargs["client_id"] == "client-id"
        assert kwargs["client_secret"] == "client-secret"  # noqa: S105
        assert kwargs["username"] == "reddit-user"
        assert kwargs["password"] == "reddit-pass"  # noqa: S105
        assert "noise-cancel" in kwargs["user_agent"]
        assert scraper.reddit is mock_reddit
        mock_reddit.user.me.assert_called_once()

    @pytest.mark.anyio
    async def test_login_resolves_env_var_references(self, app_config, monkeypatch):
        from noise_cancel.scraper.reddit import RedditScraper

        monkeypatch.setenv("NC_REDDIT_CLIENT_ID", "env-client-id")
        monkeypatch.setenv("NC_REDDIT_CLIENT_SECRET", "env-client-secret")
        monkeypatch.setenv("NC_REDDIT_USERNAME", "env-user")
        monkeypatch.setenv("NC_REDDIT_PASSWORD", "env-pass")

        app_config.scraper["platforms"]["reddit"] = {
            "enabled": True,
            "client_id": "$NC_REDDIT_CLIENT_ID",
            "client_secret": "${NC_REDDIT_CLIENT_SECRET}",
            "username": "env:NC_REDDIT_USERNAME",
            "password": "$NC_REDDIT_PASSWORD",
        }
        scraper = RedditScraper(app_config)

        mock_reddit = MagicMock()
        mock_reddit.user.me.return_value = object()
        mock_praw = MagicMock()
        mock_praw.Reddit.return_value = mock_reddit

        with patch("noise_cancel.scraper.reddit.import_module", return_value=mock_praw):
            await scraper.login()

        kwargs = mock_praw.Reddit.call_args.kwargs
        assert kwargs["client_id"] == "env-client-id"
        assert kwargs["client_secret"] == "env-client-secret"  # noqa: S105
        assert kwargs["username"] == "env-user"
        assert kwargs["password"] == "env-pass"  # noqa: S105

    @pytest.mark.anyio
    async def test_login_uses_env_fallback_when_config_missing(self, app_config, monkeypatch):
        from noise_cancel.scraper.reddit import RedditScraper

        monkeypatch.setenv("NC_REDDIT_CLIENT_ID", "fallback-client-id")
        monkeypatch.setenv("NC_REDDIT_CLIENT_SECRET", "fallback-client-secret")
        monkeypatch.setenv("NC_REDDIT_USERNAME", "fallback-user")
        monkeypatch.setenv("NC_REDDIT_PASSWORD", "fallback-pass")

        app_config.scraper["platforms"]["reddit"] = {"enabled": True}
        scraper = RedditScraper(app_config)

        mock_reddit = MagicMock()
        mock_reddit.user.me.return_value = object()
        mock_praw = MagicMock()
        mock_praw.Reddit.return_value = mock_reddit

        with patch("noise_cancel.scraper.reddit.import_module", return_value=mock_praw):
            await scraper.login()

        kwargs = mock_praw.Reddit.call_args.kwargs
        assert kwargs["client_id"] == "fallback-client-id"
        assert kwargs["client_secret"] == "fallback-client-secret"  # noqa: S105
        assert kwargs["username"] == "fallback-user"
        assert kwargs["password"] == "fallback-pass"  # noqa: S105

    @pytest.mark.anyio
    async def test_login_raises_when_credentials_missing(self, app_config):
        from noise_cancel.scraper.reddit import RedditScraper

        app_config.scraper["platforms"]["reddit"] = {"enabled": True}
        scraper = RedditScraper(app_config)

        with pytest.raises(ValueError, match="Missing Reddit credentials"):
            await scraper.login()


class TestRedditScraperFeed:
    @pytest.mark.anyio
    async def test_scrape_feed_uses_best_listing_by_default(self, app_config):
        from noise_cancel.scraper.reddit import RedditScraper

        app_config.scraper["platforms"]["reddit"] = {"enabled": True}
        scraper = RedditScraper(app_config)

        submission = _make_submission(
            post_id="abc123",
            author_name="alice",
            title="Reddit title",
            selftext="Body text",
            permalink="/r/python/comments/abc123/test_post/",
            url="https://example.com/article",
            subreddit="python",
            created_utc=1_773_000_000,
        )
        mock_front = MagicMock()
        mock_front.best.return_value = [submission]
        mock_reddit = MagicMock(front=mock_front)
        scraper._reddit = mock_reddit

        posts = await scraper.scrape_feed(scroll_count=5)

        mock_front.best.assert_called_once_with(limit=5)
        assert len(posts) == 1
        assert isinstance(posts[0], Post)
        assert posts[0].platform == "reddit"
        assert posts[0].id == "abc123"
        assert posts[0].author_name == "alice"
        assert posts[0].post_text == "Reddit title\n\nBody text"
        assert posts[0].post_url == "https://reddit.com/r/python/comments/abc123/test_post/"
        assert posts[0].metadata["subreddit"] == "python"
        assert posts[0].post_timestamp is not None

    @pytest.mark.anyio
    async def test_scrape_feed_can_use_hot_listing(self, app_config):
        from noise_cancel.scraper.reddit import RedditScraper

        app_config.scraper["platforms"]["reddit"] = {"enabled": True, "feed_sort": "hot"}
        scraper = RedditScraper(app_config)

        submission = _make_submission(
            post_id="xyz789",
            author_name=None,
            title="No author title",
            selftext="",
            permalink="/r/news/comments/xyz789/post/",
            url="https://example.com/news",
            subreddit="news",
            created_utc=1_773_000_000,
        )
        mock_front = MagicMock()
        mock_front.hot.return_value = [submission]
        mock_reddit = MagicMock(front=mock_front)
        scraper._reddit = mock_reddit

        posts = await scraper.scrape_feed(scroll_count=2)

        mock_front.hot.assert_called_once_with(limit=2)
        assert len(posts) == 1
        assert posts[0].author_name == "[deleted]"
        assert posts[0].post_text == "No author title"
        assert posts[0].metadata["subreddit"] == "news"

    @pytest.mark.anyio
    async def test_scrape_feed_logs_in_when_client_not_initialized(self, app_config):
        from noise_cancel.scraper.reddit import RedditScraper

        app_config.scraper["platforms"]["reddit"] = {"enabled": True}
        scraper = RedditScraper(app_config)

        submission = _make_submission(
            post_id="abc123",
            author_name="alice",
            title="Title",
            selftext="",
            permalink="/r/python/comments/abc123/test_post/",
            url="https://example.com/article",
            subreddit="python",
            created_utc=1_773_000_000,
        )
        mock_front = MagicMock()
        mock_front.best.return_value = [submission]
        mock_reddit = MagicMock(front=mock_front)

        async def _fake_login(headed: bool = True) -> None:
            assert headed is False
            scraper._reddit = mock_reddit

        with patch.object(scraper, "login", side_effect=_fake_login) as mock_login:
            posts = await scraper.scrape_feed(scroll_count=1)

        mock_login.assert_awaited_once_with(headed=False)
        assert len(posts) == 1

    @pytest.mark.anyio
    async def test_close_clears_client(self, app_config):
        from noise_cancel.scraper.reddit import RedditScraper

        scraper = RedditScraper(app_config)
        scraper._reddit = MagicMock()

        await scraper.close()

        assert scraper.reddit is None


def test_scraper_registry_has_reddit_mapping():
    from noise_cancel.scraper.reddit import RedditScraper
    from noise_cancel.scraper.registry import SCRAPER_REGISTRY

    assert SCRAPER_REGISTRY.get("reddit") is RedditScraper
