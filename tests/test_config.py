from pathlib import Path

import yaml

from noise_cancel.config import AppConfig, load_config


def test_default_config_creation():
    config = AppConfig()
    assert config.general["max_posts_per_run"] == 50
    assert config.classifier["model"] == "claude-haiku-4-5-20251001"
    assert config.delivery["method"] == "slack"


def test_load_config_from_yaml(tmp_path: Path):
    config_data = {
        "general": {"max_posts_per_run": 100},
        "classifier": {"model": "claude-sonnet-4-5-20250929"},
    }
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump(config_data))

    config = load_config(str(config_file))
    assert config.general["max_posts_per_run"] == 100
    assert config.classifier["model"] == "claude-sonnet-4-5-20250929"


def test_load_config_missing_file_uses_defaults():
    config = load_config("/nonexistent/path/config.yaml")
    assert config.general["max_posts_per_run"] == 50


def test_config_data_dir_default():
    config = AppConfig()
    assert "noise-cancel" in config.general["data_dir"]
