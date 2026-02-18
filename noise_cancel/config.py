from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from platformdirs import user_data_dir
from pydantic import BaseModel, Field

_DEFAULT_DATA_DIR = user_data_dir("noise-cancel")

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


_DEFAULT_CONFIG_YAML = f"""\
general:
  data_dir: {_DEFAULT_DATA_DIR}
  max_posts_per_run: 50

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
    enable_feedback_buttons: true
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
    }

    # Expand ~ in data_dir so Path("~/.local/...") resolves to the real home dir
    merged["general"]["data_dir"] = str(Path(merged["general"]["data_dir"]).expanduser())

    return AppConfig(**merged)
