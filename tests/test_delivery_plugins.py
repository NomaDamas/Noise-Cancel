from __future__ import annotations

from typing import Any

import pytest

from noise_cancel.config import AppConfig
from noise_cancel.delivery.base import DeliveryPlugin
from noise_cancel.delivery.loader import get_delivery_plugin_class
from noise_cancel.delivery.slack import SlackPlugin
from noise_cancel.models import Classification, Post


class TestDeliveryPluginBase:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            DeliveryPlugin()

    def test_subclass_must_implement_methods(self):
        class IncompletePlugin(DeliveryPlugin):
            pass

        with pytest.raises(TypeError):
            IncompletePlugin()

    def test_complete_subclass_works(self):
        class CompletePlugin(DeliveryPlugin):
            def deliver(
                self,
                posts: list[tuple[Post, Classification]],
                config: AppConfig,
            ) -> int:
                return len(posts)

            def validate_config(self, config: dict[str, Any]) -> None:
                return None

        plugin = CompletePlugin()
        assert plugin.deliver([], AppConfig()) == 0
        plugin.validate_config({})


class TestDeliveryPluginLoader:
    def test_returns_slack_plugin_class(self):
        plugin_class = get_delivery_plugin_class("slack")
        assert plugin_class is SlackPlugin
        assert issubclass(plugin_class, DeliveryPlugin)

    def test_raises_for_unknown_type(self):
        with pytest.raises(ValueError, match="Unknown delivery plugin type"):
            get_delivery_plugin_class("does-not-exist")
