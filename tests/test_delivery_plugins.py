from __future__ import annotations

import os
from typing import Any
from unittest.mock import patch

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


class TestSlackPlugin:
    def test_deliver_delegates_to_deliver_posts(self):
        plugin = SlackPlugin()
        config = AppConfig()

        with patch("noise_cancel.delivery.slack.deliver_posts", return_value=3) as mock_deliver:
            delivered_count = plugin.deliver([], config)

        assert delivered_count == 3
        mock_deliver.assert_called_once_with([], config)

    def test_validate_config_raises_without_webhook(self):
        plugin = SlackPlugin()

        with patch.dict(os.environ, {}, clear=True), pytest.raises(ValueError, match="webhook_url"):
            plugin.validate_config({"type": "slack"})

    def test_validate_config_accepts_plugin_webhook(self):
        plugin = SlackPlugin()

        with patch.dict(os.environ, {}, clear=True):
            plugin.validate_config({"type": "slack", "webhook_url": "https://hooks.slack.com/services/test"})

    def test_validate_config_accepts_env_webhook(self):
        plugin = SlackPlugin()

        with patch.dict(os.environ, {"SLACK_WEBHOOK_URL": "https://hooks.slack.com/services/test"}, clear=True):
            plugin.validate_config({"type": "slack"})
