from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from platformdirs import user_data_dir
from pydantic import BaseModel, Field, model_validator

_DEFAULT_DATA_DIR = user_data_dir("noise-cancel")

_DEFAULT_GENERAL: dict[str, Any] = {
    "data_dir": _DEFAULT_DATA_DIR,
    "max_posts_per_run": 50,
    "language": "english",
}

_DEFAULT_SCRAPER: dict[str, Any] = {
    "headless": True,
    "scroll_count": 10,
    "scroll_delay_min": 1.5,
    "scroll_delay_max": 3.5,
    "session_ttl_days": 7,
}

_DEFAULT_CLASSIFIER: dict[str, Any] = {
    "model": "claude-sonnet-4-6",
    "batch_size": 10,
    "temperature": 0.0,
    "categories": [
        {
            "name": "Read",
            "description": "Worth reading - valuable insights, relevant industry news, useful knowledge",
            "emoji": ":fire:",
        },
        {
            "name": "Skip",
            "description": "Not worth reading - engagement bait, humble brag, ads, spam, irrelevant",
            "emoji": ":mute:",
        },
    ],
    "whitelist": {"keywords": [], "authors": []},
    "blacklist": {"keywords": [], "authors": []},
}

_DEFAULT_DELIVERY: dict[str, Any] = {
    "method": "slack",
    "slack": {
        "include_categories": ["Read"],
        "include_reasoning": True,
        "max_text_preview": 300,
    },
}

_DEFAULT_SERVER: dict[str, Any] = {
    "cors_origins": ["*"],
}


def _legacy_delivery_to_plugins(delivery: dict[str, Any]) -> list[dict[str, Any]]:
    method = delivery.get("method")
    if not isinstance(method, str) or not method:
        return []

    plugin_config = delivery.get(method, {})
    plugin_entry: dict[str, Any] = {"type": method}
    if isinstance(plugin_config, dict):
        plugin_entry.update(plugin_config)
    return [plugin_entry]


def _normalize_delivery_config(delivery: dict[str, Any]) -> dict[str, Any]:
    normalized = _deep_merge(_DEFAULT_DELIVERY, delivery)
    plugins = normalized.get("plugins")

    normalized_plugins: list[dict[str, Any]]
    if isinstance(plugins, list) and plugins:
        normalized_plugins = [dict(plugin) for plugin in plugins if isinstance(plugin, dict)]
    else:
        normalized_plugins = _legacy_delivery_to_plugins(normalized)

    normalized["plugins"] = normalized_plugins

    if len(normalized_plugins) == 1:
        plugin_type = normalized_plugins[0].get("type")
        if isinstance(plugin_type, str) and plugin_type:
            normalized["method"] = plugin_type

    slack_plugin = next(
        (
            plugin
            for plugin in normalized_plugins
            if isinstance(plugin.get("type"), str) and plugin["type"].strip().lower() == "slack"
        ),
        None,
    )
    if slack_plugin is not None:
        plugin_slack_config = {k: v for k, v in slack_plugin.items() if k != "type"}
        normalized["slack"] = _deep_merge(_DEFAULT_DELIVERY["slack"], plugin_slack_config)

    return normalized


class AppConfig(BaseModel):
    general: dict[str, Any] = Field(default_factory=lambda: dict(_DEFAULT_GENERAL))
    scraper: dict[str, Any] = Field(default_factory=lambda: dict(_DEFAULT_SCRAPER))
    classifier: dict[str, Any] = Field(default_factory=lambda: dict(_DEFAULT_CLASSIFIER))
    delivery: dict[str, Any] = Field(default_factory=lambda: dict(_DEFAULT_DELIVERY))
    server: dict[str, Any] = Field(default_factory=lambda: dict(_DEFAULT_SERVER))

    @model_validator(mode="after")
    def normalize_delivery(self) -> AppConfig:
        self.delivery = _normalize_delivery_config(self.delivery)
        return self


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


_DEFAULT_CONFIG_YAML = f"""\
general:
  data_dir: {_DEFAULT_DATA_DIR}
  max_posts_per_run: 50
  language: english  # Summary language: english, korean, japanese, etc.

scraper:
  headless: true
  scroll_count: 10
  scroll_delay_min: 1.5
  scroll_delay_max: 3.5
  session_ttl_days: 7

classifier:
  model: claude-sonnet-4-6
  batch_size: 10
  temperature: 0.0
  categories:
    - name: Read
      description: "Worth reading - valuable insights, relevant industry news, useful knowledge"
      emoji: ":fire:"
    - name: Skip
      description: "Not worth reading - engagement bait, humble brag, ads, spam, irrelevant"
      emoji: ":mute:"
  whitelist:
    keywords: []     # Posts containing these keywords are always Read
    authors: []      # Posts by these authors are always Read
  blacklist:
    keywords: []     # Posts containing these keywords are always Skip
    authors: []      # Posts by these authors are always Skip

delivery:
  method: slack
  slack:
    include_categories:
      - Read
    include_reasoning: true
    max_text_preview: 300

server:
  cors_origins:
    - "*"
"""


def default_config_path() -> Path:
    return Path.home() / ".config" / "noise-cancel" / "config.yaml"


def generate_default_config(config_path: Path | None = None) -> Path:
    """Write the default config YAML to disk. Return the path written."""
    path = config_path or default_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_DEFAULT_CONFIG_YAML)
    return path


def load_config(config_path: str | None = None) -> AppConfig:
    if config_path is None:
        config_path = os.environ.get("NC_CONFIG_PATH", str(default_config_path()))

    raw: dict[str, Any] = {}
    path = Path(config_path)
    if path.exists():
        with open(path) as f:
            loaded = yaml.safe_load(f)
            if isinstance(loaded, dict):
                raw = loaded

    merged = {
        "general": _deep_merge(_DEFAULT_GENERAL, raw.get("general", {})),
        "scraper": _deep_merge(_DEFAULT_SCRAPER, raw.get("scraper", {})),
        "classifier": _deep_merge(_DEFAULT_CLASSIFIER, raw.get("classifier", {})),
        "delivery": _deep_merge(_DEFAULT_DELIVERY, raw.get("delivery", {})),
        "server": _deep_merge(_DEFAULT_SERVER, raw.get("server", {})),
    }

    # Expand ~ in data_dir so Path("~/.local/...") resolves to the real home dir
    merged["general"]["data_dir"] = str(Path(merged["general"]["data_dir"]).expanduser())

    return AppConfig(**merged)
