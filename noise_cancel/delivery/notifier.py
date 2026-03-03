from __future__ import annotations

import sys

from noise_cancel.config import AppConfig
from noise_cancel.delivery.loader import get_delivery_plugin_class


def notify_plugins(
    message: str,
    config: AppConfig,
    *,
    stderr_fallback: bool = True,
) -> bool:
    plugins = config.delivery.get("plugins", [])

    delivered = False
    has_configured_plugins = False

    for plugin_config in plugins:
        if not isinstance(plugin_config, dict):
            continue

        plugin_type = plugin_config.get("type")
        if not isinstance(plugin_type, str) or not plugin_type.strip():
            continue

        has_configured_plugins = True
        plugin_class = get_delivery_plugin_class(plugin_type)
        plugin = plugin_class()
        plugin.validate_config(plugin_config)
        delivered = plugin.notify(message, config, plugin_config) or delivered

    if stderr_fallback and not has_configured_plugins:
        print(message, file=sys.stderr)

    return delivered
