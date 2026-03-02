from __future__ import annotations

from noise_cancel.scraper.base import AbstractScraper


class ScraperRegistry:
    def __init__(self) -> None:
        self._registry: dict[str, type[AbstractScraper]] = {}

    def register(self, platform: str, scraper_class: type[AbstractScraper]) -> None:
        key = platform.strip().lower()
        if not key:
            msg = "Platform name cannot be empty"
            raise ValueError(msg)
        self._registry[key] = scraper_class

    def get(self, platform: str) -> type[AbstractScraper]:
        key = platform.strip().lower()
        scraper_class = self._registry.get(key)
        if scraper_class is None:
            msg = f"No scraper registered for platform '{platform}'"
            raise KeyError(msg)
        return scraper_class

    def mappings(self) -> dict[str, type[AbstractScraper]]:
        return dict(self._registry)


SCRAPER_REGISTRY = ScraperRegistry()


def _register_builtin_scrapers() -> None:
    from noise_cancel.scraper.linkedin import LinkedInScraper
    from noise_cancel.scraper.threads import ThreadsScraper
    from noise_cancel.scraper.x import XScraper

    SCRAPER_REGISTRY.register("linkedin", LinkedInScraper)
    SCRAPER_REGISTRY.register("threads", ThreadsScraper)
    SCRAPER_REGISTRY.register("x", XScraper)


_register_builtin_scrapers()
