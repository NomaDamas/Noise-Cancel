from __future__ import annotations

from abc import ABC, abstractmethod

from noise_cancel.models import Post


class AbstractScraper(ABC):
    @abstractmethod
    async def login(self, headed: bool = True) -> None: ...

    @abstractmethod
    async def scrape_feed(self, scroll_count: int = 10) -> list[Post]: ...

    @abstractmethod
    async def close(self) -> None: ...
