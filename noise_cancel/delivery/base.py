from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from noise_cancel.config import AppConfig
from noise_cancel.models import Classification, Post


class DeliveryPlugin(ABC):
    @abstractmethod
    def deliver(
        self,
        posts: list[tuple[Post, Classification]],
        config: AppConfig,
    ) -> int: ...

    @abstractmethod
    def validate_config(self, config: dict[str, Any]) -> None: ...
