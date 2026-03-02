from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from noise_cancel.models import Post

_RSS_FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "rss"


def _fixture_bytes(name: str) -> bytes:
    return (_RSS_FIXTURE_DIR / name).read_bytes()


def _response(url: str, *, status_code: int, body: bytes) -> httpx.Response:
    return httpx.Response(status_code=status_code, content=body, request=httpx.Request("GET", url))


def _async_client_factory(
    responses: dict[str, object],
    requested_urls: list[str],
) -> type:
    class _PatchedAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            del args, kwargs

        async def __aenter__(self) -> _PatchedAsyncClient:
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            del exc_type, exc, tb
            return None

        async def get(self, url: str) -> httpx.Response:
            requested_urls.append(url)
            result = responses.get(url)
            if result is None:
                msg = f"Unexpected URL requested in test: {url}"
                raise AssertionError(msg)
            if isinstance(result, Exception):
                raise result
            assert isinstance(result, httpx.Response)
            return result

    return _PatchedAsyncClient


@pytest.mark.anyio
async def test_login_and_close_are_noops(app_config):
    from noise_cancel.scraper.base import AbstractScraper
    from noise_cancel.scraper.rss import RssScraper

    scraper = RssScraper(app_config)

    assert isinstance(scraper, AbstractScraper)
    assert await scraper.login() is None
    assert await scraper.close() is None


@pytest.mark.anyio
async def test_scrape_feed_fetches_all_configured_urls(app_config):
    from noise_cancel.scraper.rss import RssScraper

    first_url = "https://example.com/atom.xml"
    second_url = "https://example.net/atom.xml"
    app_config.scraper["platforms"]["rss"] = {
        "enabled": True,
        "feeds": [
            {"url": first_url, "name": "First Feed"},
            {"url": second_url, "name": "Second Feed"},
        ],
    }
    responses = {
        first_url: _response(first_url, status_code=200, body=_fixture_bytes("atom_valid.xml")),
        second_url: _response(second_url, status_code=200, body=_fixture_bytes("atom_second.xml")),
    }
    requested_urls: list[str] = []
    scraper = RssScraper(app_config)

    with patch(
        "noise_cancel.scraper.rss.httpx.AsyncClient",
        _async_client_factory(responses, requested_urls),
    ):
        posts = await scraper.scrape_feed(scroll_count=123)

    assert requested_urls == [first_url, second_url]
    assert len(posts) == 3


@pytest.mark.anyio
async def test_scrape_feed_maps_entries_to_posts(app_config):
    from noise_cancel.scraper.rss import RssScraper

    feed_url = "https://example.com/atom.xml"
    app_config.scraper["platforms"]["rss"] = {
        "enabled": True,
        "feeds": [{"url": feed_url, "name": "Sample Feed"}],
    }
    responses = {
        feed_url: _response(feed_url, status_code=200, body=_fixture_bytes("atom_valid.xml")),
    }
    scraper = RssScraper(app_config)

    with patch("noise_cancel.scraper.rss.httpx.AsyncClient", _async_client_factory(responses, [])):
        posts = await scraper.scrape_feed()

    assert len(posts) == 2
    assert all(isinstance(post, Post) for post in posts)

    first, second = posts
    assert first.platform == "rss"
    assert first.id == "tag:example.com,2025:1"
    assert first.author_name == "Alice"
    assert first.post_text == "Summary one"
    assert first.post_url == "https://example.com/posts/1"

    assert second.platform == "rss"
    assert second.id == "tag:example.com,2025:2"
    assert second.author_name == "Feed Author"
    assert second.post_text == "Full content two"
    assert second.post_url == "https://example.com/posts/2"


@pytest.mark.anyio
async def test_scrape_feed_handles_timeout_malformed_xml_and_404(app_config):
    from noise_cancel.scraper.rss import RssScraper

    timeout_url = "https://example.com/timeout.xml"
    malformed_url = "https://example.com/malformed.xml"
    missing_url = "https://example.com/not-found.xml"
    valid_url = "https://example.com/atom.xml"

    app_config.scraper["platforms"]["rss"] = {
        "enabled": True,
        "feeds": [
            {"url": timeout_url, "name": "Timeout Feed"},
            {"url": malformed_url, "name": "Malformed Feed"},
            {"url": missing_url, "name": "Missing Feed"},
            {"url": valid_url, "name": "Valid Feed"},
        ],
    }

    responses = {
        timeout_url: httpx.ReadTimeout(
            "timeout",
            request=httpx.Request("GET", timeout_url),
        ),
        malformed_url: _response(malformed_url, status_code=200, body=_fixture_bytes("malformed.xml")),
        missing_url: _response(missing_url, status_code=404, body=b"Not Found"),
        valid_url: _response(valid_url, status_code=200, body=_fixture_bytes("atom_valid.xml")),
    }
    requested_urls: list[str] = []
    scraper = RssScraper(app_config)

    with patch("noise_cancel.scraper.rss.httpx.AsyncClient", _async_client_factory(responses, requested_urls)):
        posts = await scraper.scrape_feed()

    assert requested_urls == [timeout_url, malformed_url, missing_url, valid_url]
    assert len(posts) == 2
    assert all(post.platform == "rss" for post in posts)


def test_scraper_registry_has_rss_mapping():
    from noise_cancel.scraper.registry import SCRAPER_REGISTRY
    from noise_cancel.scraper.rss import RssScraper

    assert SCRAPER_REGISTRY.get("rss") is RssScraper
