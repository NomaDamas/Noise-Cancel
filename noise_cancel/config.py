from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

_DEFAULT_DATA_DIR = str(Path.home() / ".local" / "share" / "noise-cancel")

_DEFAULT_GENERAL: dict[str, Any] = {
    "data_dir": _DEFAULT_DATA_DIR,
    "max_posts_per_run": 50,
}

_DEFAULT_SCRAPER: dict[str, Any] = {
    "headless": True,
    "scroll_count": 10,
    "scroll_delay_min": 1.5,
    "scroll_delay_max": 3.5,
    "session_ttl_days": 7,
}

_DEFAULT_CLASSIFIER: dict[str, Any] = {
    "model": "claude-haiku-4-5-20251001",
    "batch_size": 10,
    "temperature": 0.0,
    "categories": [
        {"name": "Must Read", "description": "High-value content directly relevant to interests", "emoji": ":fire:"},
        {"name": "Interesting", "description": "Worth a quick look, indirectly helpful", "emoji": ":eyes:"},
        {"name": "Noise", "description": "Engagement bait, humble brag, not worth reading", "emoji": ":mute:"},
        {"name": "Spam", "description": "Ads, sales, irrelevant promotions", "emoji": ":no_entry:"},
    ],
    "rules": [],
}

_DEFAULT_DELIVERY: dict[str, Any] = {
    "method": "slack",
    "slack": {
        "include_categories": ["Must Read", "Interesting"],
        "include_reasoning": True,
        "max_text_preview": 300,
        "enable_feedback_buttons": True,
    },
}


class AppConfig(BaseModel):
    general: dict[str, Any] = Field(default_factory=lambda: dict(_DEFAULT_GENERAL))
    scraper: dict[str, Any] = Field(default_factory=lambda: dict(_DEFAULT_SCRAPER))
    classifier: dict[str, Any] = Field(default_factory=lambda: dict(_DEFAULT_CLASSIFIER))
    delivery: dict[str, Any] = Field(default_factory=lambda: dict(_DEFAULT_DELIVERY))


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(config_path: str | None = None) -> AppConfig:
    if config_path is None:
        config_path = os.environ.get(
            "NC_CONFIG_PATH",
            str(Path.home() / ".config" / "noise-cancel" / "config.yaml"),
        )

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
    }

    return AppConfig(**merged)
