from __future__ import annotations

from noise_cancel.delivery.base import DeliveryPlugin
from noise_cancel.delivery.slack import SlackPlugin

_PLUGIN_REGISTRY: dict[str, type[DeliveryPlugin]] = {
    "slack": SlackPlugin,
}


class UnknownDeliveryPluginError(ValueError):
    def __init__(self, plugin_type: str) -> None:
        super().__init__(f"Unknown delivery plugin type: {plugin_type}")


def get_delivery_plugin_class(plugin_type: str) -> type[DeliveryPlugin]:
    plugin_key = plugin_type.strip().lower()
    plugin_class = _PLUGIN_REGISTRY.get(plugin_key)
    if plugin_class is None:
        raise UnknownDeliveryPluginError(plugin_type)
    return plugin_class
