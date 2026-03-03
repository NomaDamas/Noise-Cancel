from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from noise_cancel.models import Post


def _mock_playwright_chain(storage_state: dict | None = None):
    """Build a mock Playwright async API chain for login testing."""
    mock_storage = storage_state if storage_state is not None else {"cookies": []}

    mock_page = AsyncMock()
    mock_context = AsyncMock()
    mock_context.storage_state = AsyncMock(return_value=mock_storage)
    mock_context.new_page = AsyncMock(return_value=mock_page)

    mock_browser = AsyncMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)

    mock_pw = AsyncMock()
    mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)

    mock_cm = MagicMock()
    mock_cm.start = AsyncMock(return_value=mock_pw)

    mock_module = MagicMock()
    mock_module.async_playwright.return_value = mock_cm

    return mock_module, mock_pw, mock_browser, mock_context, mock_page


def _mock_scrape_playwright(*, current_url: str = "https://x.com/home", raw_posts: list[dict] | None = None):
    """Build a mock Playwright chain suitable for scrape_feed testing."""
    mock_page = AsyncMock()
    type(mock_page).url = PropertyMock(return_value=current_url)
    mock_page.evaluate = AsyncMock(return_value=raw_posts or [])
    mock_page.mouse = AsyncMock()

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)

    mock_browser = AsyncMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)

    mock_pw = AsyncMock()
    mock_pw.chromium.launch = AsyncMock(return_value=mock_browser)

    mock_cm = MagicMock()
    mock_cm.start = AsyncMock(return_value=mock_pw)

    mock_module = MagicMock()
    mock_module.async_playwright.return_value = mock_cm

    return mock_module, mock_pw, mock_browser, mock_context, mock_page


class TestXScraperLogin:
    @pytest.mark.anyio
    async def test_login_persists_encrypted_session(self, app_config):
        from noise_cancel.scraper.auth import load_session
        from noise_cancel.scraper.x import XScraper

        scraper = XScraper(app_config)
        storage = {"cookies": [{"name": "auth_token", "value": "abc123"}]}
        mock_module, mock_pw, mock_browser, _, mock_page = _mock_playwright_chain(storage)

        with patch("noise_cancel.scraper.playwright_base.import_module", return_value=mock_module):
            await scraper.login(headed=True)

        data_dir = Path(app_config.general["data_dir"])
        key_path = data_dir / "x_session.key"
        session_path = data_dir / "x_session.enc"
        assert key_path.exists()
        assert session_path.exists()

        key = key_path.read_text().strip()
        loaded = load_session(key, str(session_path))
        assert loaded == storage
        assert scraper.storage_state == storage

        mock_pw.chromium.launch.assert_called_once_with(headless=False)
        mock_page.goto.assert_called_once_with("https://x.com", wait_until="domcontentloaded")
        mock_page.wait_for_url.assert_called_once()
        mock_browser.close.assert_called_once()
        mock_pw.stop.assert_called_once()

    @pytest.mark.anyio
    async def test_login_headed_false_passes_headless_true(self, app_config):
        from noise_cancel.scraper.x import XScraper

        scraper = XScraper(app_config)
        mock_module, mock_pw, *_ = _mock_playwright_chain()

        with patch("noise_cancel.scraper.playwright_base.import_module", return_value=mock_module):
            await scraper.login(headed=False)

        mock_pw.chromium.launch.assert_called_once_with(headless=True)

    @pytest.mark.anyio
    async def test_login_stops_playwright_on_error(self, app_config):
        from noise_cancel.scraper.x import XScraper

        scraper = XScraper(app_config)
        mock_module, mock_pw, _, _, mock_page = _mock_playwright_chain()
        mock_page.goto.side_effect = RuntimeError("Connection failed")

        with (
            patch("noise_cancel.scraper.playwright_base.import_module", return_value=mock_module),
            pytest.raises(RuntimeError, match="Connection failed"),
        ):
            await scraper.login()

        mock_pw.stop.assert_called_once()


class TestXScraperScrapeFeed:
    @pytest.mark.anyio
    async def test_scrape_feed_loads_stored_session(self, app_config):
        from noise_cancel.scraper.x import XScraper

        scraper = XScraper(app_config)
        mock_module, _, _, mock_context, mock_page = _mock_scrape_playwright()

        with (
            patch("noise_cancel.scraper.playwright_base.import_module", return_value=mock_module),
            patch(
                "noise_cancel.scraper.playwright_base.validate_session", return_value={"cookies": []}
            ) as mock_validate,
            patch("noise_cancel.scraper.playwright_base.random_viewport", return_value={"width": 1280, "height": 720}),
            patch("noise_cancel.scraper.playwright_base.human_scroll_sequence", return_value=[]),
            patch("noise_cancel.scraper.playwright_base.random_delay", return_value=0.0),
        ):
            await scraper.scrape_feed(scroll_count=0)

        data_dir = Path(app_config.general["data_dir"])
        mock_validate.assert_called_once_with(
            key_path=str(data_dir / "x_session.key"),
            session_path=str(data_dir / "x_session.enc"),
            ttl_days=7,
        )
        mock_context.new_page.assert_called_once()
        mock_page.goto.assert_called_once_with("https://x.com/home", wait_until="domcontentloaded")

    @pytest.mark.anyio
    async def test_scrape_feed_scrolls_with_humanized_actions(self, app_config):
        from noise_cancel.scraper.x import XScraper

        scraper = XScraper(app_config)
        scroll_actions = [
            {"scroll_y": 500, "delay": 0.0, "direction": "down"},
            {"scroll_y": 300, "delay": 0.0, "direction": "up"},
        ]
        mock_module, _, _, _, mock_page = _mock_scrape_playwright()

        with (
            patch("noise_cancel.scraper.playwright_base.import_module", return_value=mock_module),
            patch("noise_cancel.scraper.playwright_base.validate_session", return_value={"cookies": []}),
            patch("noise_cancel.scraper.playwright_base.random_viewport", return_value={"width": 1280, "height": 720}),
            patch("noise_cancel.scraper.playwright_base.human_scroll_sequence", return_value=scroll_actions),
            patch("noise_cancel.scraper.playwright_base.random_delay", return_value=0.0),
            patch("noise_cancel.scraper.playwright_base.asyncio.sleep", new_callable=AsyncMock),
        ):
            await scraper.scrape_feed(scroll_count=2)

        calls = mock_page.mouse.wheel.call_args_list
        assert len(calls) == 2
        assert calls[0].args == (0, 500)
        assert calls[1].args == (0, -300)

    @pytest.mark.anyio
    async def test_scrape_feed_extracts_and_deduplicates_posts(self, app_config):
        from noise_cancel.scraper.x import XScraper

        raw = [
            {
                "id": "111",
                "author_name": "Alice",
                "post_text": "Hello",
                "post_url": "https://x.com/alice/status/111",
                "post_timestamp": "2026-03-01T12:00:00.000Z",
            },
            {
                "id": "111",
                "author_name": "Alice",
                "post_text": "Hello",
                "post_url": "https://x.com/alice/status/111",
                "post_timestamp": "2026-03-01T12:00:00.000Z",
            },
            {
                "id": "",
                "author_name": "Bob",
                "post_text": "World",
                "post_url": "https://x.com/bob/status/222",
                "post_timestamp": "2026-03-01T12:05:00.000Z",
            },
            {
                "id": "333",
                "author_name": "Charlie",
                "post_text": "",
                "post_url": "https://x.com/charlie/status/333",
            },
        ]
        scraper = XScraper(app_config)
        mock_module, _, _, _, _ = _mock_scrape_playwright(raw_posts=raw)

        with (
            patch("noise_cancel.scraper.playwright_base.import_module", return_value=mock_module),
            patch("noise_cancel.scraper.playwright_base.validate_session", return_value={"cookies": []}),
            patch("noise_cancel.scraper.playwright_base.random_viewport", return_value={"width": 1280, "height": 720}),
            patch("noise_cancel.scraper.playwright_base.human_scroll_sequence", return_value=[]),
            patch("noise_cancel.scraper.playwright_base.random_delay", return_value=0.0),
        ):
            posts = await scraper.scrape_feed(scroll_count=0)

        assert len(posts) == 2
        assert all(isinstance(post, Post) for post in posts)
        assert [post.id for post in posts] == ["111", "222"]
        assert all(post.platform == "x" for post in posts)

    @pytest.mark.anyio
    async def test_scrape_feed_raises_on_login_redirect(self, app_config):
        from noise_cancel.scraper.x import XScraper

        scraper = XScraper(app_config)
        mock_module, _, _, _, _ = _mock_scrape_playwright(current_url="https://x.com/i/flow/login")

        with (
            patch("noise_cancel.scraper.playwright_base.import_module", return_value=mock_module),
            patch("noise_cancel.scraper.playwright_base.validate_session", return_value={"cookies": []}),
            patch("noise_cancel.scraper.playwright_base.random_viewport", return_value={"width": 1280, "height": 720}),
            pytest.raises(RuntimeError, match="Session expired"),
        ):
            await scraper.scrape_feed(scroll_count=0)

    @pytest.mark.anyio
    async def test_scrape_feed_propagates_session_validation_errors(self, app_config):
        from noise_cancel.scraper.x import XScraper

        scraper = XScraper(app_config)
        mock_module, _, _, _, _ = _mock_scrape_playwright()

        with (
            patch("noise_cancel.scraper.playwright_base.import_module", return_value=mock_module),
            patch(
                "noise_cancel.scraper.playwright_base.validate_session", side_effect=RuntimeError("No session found")
            ),
            pytest.raises(RuntimeError, match="No session found"),
        ):
            await scraper.scrape_feed(scroll_count=0)


class TestXScraperHelpers:
    def test_parse_post_element_sets_platform_to_x(self, app_config):
        from noise_cancel.scraper.x import XScraper

        scraper = XScraper(app_config)
        post = scraper.parse_post_element({
            "id": "12345",
            "author_name": "Alice",
            "post_text": "Hello from X",
            "post_url": "https://x.com/alice/status/12345",
            "post_timestamp": "2026-03-01T12:00:00.000Z",
        })

        assert post.id == "12345"
        assert post.platform == "x"
        assert post.post_url == "https://x.com/alice/status/12345"

    @pytest.mark.anyio
    async def test_close_stops_playwright_instance(self, app_config):
        from noise_cancel.scraper.x import XScraper

        scraper = XScraper(app_config)
        mock_pw = AsyncMock()
        scraper._playwright = mock_pw

        await scraper.close()

        mock_pw.stop.assert_called_once()
        assert scraper._playwright is None


def test_scraper_registry_has_x_mapping():
    from noise_cancel.scraper.registry import SCRAPER_REGISTRY
    from noise_cancel.scraper.x import XScraper

    assert SCRAPER_REGISTRY.get("x") is XScraper
