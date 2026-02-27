from pathlib import Path

import yaml

from noise_cancel.config import AppConfig, generate_default_config, load_config


def test_default_config_creation():
    config = AppConfig()
    assert config.general["max_posts_per_run"] == 50
    assert config.classifier["model"] == "claude-sonnet-4-6"
    assert config.delivery["plugins"][0]["type"] == "slack"
    assert config.server["cors_origins"] == ["*"]


def test_load_config_from_yaml(tmp_path: Path):
    config_data = {
        "general": {"max_posts_per_run": 100},
        "classifier": {"model": "claude-sonnet-4-5-20250929"},
        "server": {"cors_origins": ["https://app.example.com"]},
    }
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump(config_data))

    config = load_config(str(config_file))
    assert config.general["max_posts_per_run"] == 100
    assert config.classifier["model"] == "claude-sonnet-4-5-20250929"
    assert config.server["cors_origins"] == ["https://app.example.com"]


def test_load_config_missing_file_uses_defaults():
    config = load_config("/nonexistent/path/config.yaml")
    assert config.general["max_posts_per_run"] == 50


def test_config_data_dir_default():
    config = AppConfig()
    assert "noise-cancel" in config.general["data_dir"]


def test_generate_default_config(tmp_path: Path):
    path = tmp_path / "sub" / "config.yaml"
    result = generate_default_config(path)
    assert result == path
    assert path.exists()
    loaded = yaml.safe_load(path.read_text())
    assert loaded["classifier"]["model"] == "claude-sonnet-4-6"
    assert len(loaded["classifier"]["categories"]) == 2
    assert loaded["classifier"]["categories"][0]["name"] == "Read"
    assert loaded["classifier"]["categories"][1]["name"] == "Skip"


def test_generate_default_config_is_loadable(tmp_path: Path):
    path = tmp_path / "config.yaml"
    generate_default_config(path)
    config = load_config(str(path))
    assert config.classifier["model"] == "claude-sonnet-4-6"
    assert config.delivery["slack"]["include_categories"] == ["Read"]
    assert config.delivery["plugins"][0]["type"] == "slack"
    assert config.server["cors_origins"] == ["*"]


def test_load_config_supports_plugins_format(tmp_path: Path):
    config_data = {
        "delivery": {
            "plugins": [
                {
                    "type": "slack",
                    "include_categories": ["Read", "Skip"],
                    "include_reasoning": False,
                }
            ]
        }
    }
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump(config_data))

    config = load_config(str(config_file))
    plugins = config.delivery["plugins"]

    assert len(plugins) == 1
    assert plugins[0]["type"] == "slack"
    assert plugins[0]["include_categories"] == ["Read", "Skip"]
    assert plugins[0]["include_reasoning"] is False


def test_load_config_converts_legacy_delivery_to_plugins(tmp_path: Path):
    config_data = {
        "delivery": {
            "method": "slack",
            "slack": {
                "include_categories": ["Read", "Skip"],
                "include_reasoning": False,
            },
        }
    }
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump(config_data))

    config = load_config(str(config_file))
    plugins = config.delivery["plugins"]

    assert len(plugins) == 1
    assert plugins[0]["type"] == "slack"
    assert plugins[0]["include_categories"] == ["Read", "Skip"]
    assert plugins[0]["include_reasoning"] is False


def test_app_config_converts_legacy_delivery_to_plugins():
    config = AppConfig(
        delivery={
            "method": "slack",
            "slack": {
                "include_categories": ["Read"],
                "include_reasoning": True,
                "max_text_preview": 300,
            },
        }
    )

    plugins = config.delivery["plugins"]
    assert len(plugins) == 1
    assert plugins[0]["type"] == "slack"
    assert plugins[0]["include_categories"] == ["Read"]


def test_load_config_uses_default_server_cors_origins(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump({"general": {"max_posts_per_run": 75}}))

    config = load_config(str(config_file))

    assert config.server["cors_origins"] == ["*"]
