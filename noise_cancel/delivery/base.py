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

    def deliver_digest(
        self,
        digest_text: str,
        config: AppConfig,
        plugin_config: dict[str, Any],
    ) -> bool:
        del digest_text, config, plugin_config
        return False

    def notify(
        self,
        message: str,
        config: AppConfig,
        plugin_config: dict[str, Any],
    ) -> bool:
        del message, config, plugin_config
        return False
