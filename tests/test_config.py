from pathlib import Path

import pytest
import yaml

from noise_cancel.config import AppConfig, ConfigError, generate_default_config, load_config


def test_default_config_creation():
    config = AppConfig()
    assert config.general["max_posts_per_run"] == 50
    assert config.classifier["model"] == "claude-sonnet-4-6"
    assert config.delivery["plugins"][0]["type"] == "slack"
    assert config.dedup["semantic"]["enabled"] is False
    assert config.dedup["semantic"]["provider"] == "sentence-transformers"
    assert config.dedup["semantic"]["model"] == "all-MiniLM-L6-v2"
    assert config.dedup["semantic"]["threshold"] == 0.85
    assert config.server["cors_origins"] == ["*"]
    assert config.server["api_key"] == ""


def test_load_config_from_yaml(tmp_path: Path):
    config_data = {
        "general": {"max_posts_per_run": 100},
        "classifier": {"model": "claude-sonnet-4-5-20250929"},
        "server": {"cors_origins": ["https://app.example.com"], "api_key": "test-key"},
    }
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump(config_data))

    config = load_config(str(config_file))
    assert config.general["max_posts_per_run"] == 100
    assert config.classifier["model"] == "claude-sonnet-4-5-20250929"
    assert config.server["cors_origins"] == ["https://app.example.com"]
    assert config.server["api_key"] == "test-key"


def test_load_config_missing_file_uses_defaults():
    config = load_config("/nonexistent/path/config.yaml")
    assert config.general["max_posts_per_run"] == 50


def test_load_config_raises_config_error_for_invalid_whitelist_regex(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        yaml.dump({
            "classifier": {
                "whitelist": {
                    "keywords": ["("],
                    "authors": [],
                }
            }
        })
    )

    with pytest.raises(ConfigError) as exc_info:
        load_config(str(config_file))

    message = str(exc_info.value)
    assert "Invalid regex pattern" in message
    assert "'('" in message


def test_load_config_accepts_regex_patterns(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        yaml.dump({
            "classifier": {
                "whitelist": {
                    "keywords": [r"(?i)\bAI\b", r"^Breaking:"],
                    "authors": [r"Yann\s+LeCun"],
                },
                "blacklist": {
                    "keywords": [r"\b(agree|thoughts)\?"],
                    "authors": [],
                },
            }
        })
    )

    config = load_config(str(config_file))

    assert config.classifier["whitelist"]["keywords"] == [r"(?i)\bAI\b", r"^Breaking:"]


def test_load_config_accepts_platform_specific_classifier_prompts(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        yaml.dump({
            "classifier": {
                "platform_prompts": {
                    "x": {"system_prompt": "Classify short-form posts with hashtag context."},
                    "reddit": {"system_prompt": "Classify posts with subreddit-style discussion context."},
                }
            }
        })
    )

    config = load_config(str(config_file))

    assert config.classifier["platform_prompts"]["x"]["system_prompt"].startswith("Classify short-form")
    assert config.classifier["platform_prompts"]["reddit"]["system_prompt"].startswith("Classify posts with subreddit")


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
    assert config.dedup["semantic"]["enabled"] is False
    assert config.dedup["semantic"]["provider"] == "sentence-transformers"
    assert config.dedup["semantic"]["model"] == "all-MiniLM-L6-v2"
    assert config.dedup["semantic"]["threshold"] == 0.85
    assert config.server["cors_origins"] == ["*"]
    assert config.server["api_key"] == ""


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


def test_load_config_uses_default_server_api_key(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump({"general": {"max_posts_per_run": 75}}))

    config = load_config(str(config_file))

    assert config.server["api_key"] == ""


def test_load_config_supports_semantic_dedup_overrides(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        yaml.dump({
            "dedup": {
                "semantic": {
                    "enabled": True,
                    "provider": "openai",
                    "model": "text-embedding-3-small",
                    "threshold": 0.91,
                }
            }
        })
    )

    config = load_config(str(config_file))

    assert config.dedup["semantic"]["enabled"] is True
    assert config.dedup["semantic"]["provider"] == "openai"
    assert config.dedup["semantic"]["model"] == "text-embedding-3-small"
    assert config.dedup["semantic"]["threshold"] == 0.91


def test_default_scraper_config_has_linkedin_platform():
    config = AppConfig()

    assert "platforms" in config.scraper
    assert "linkedin" in config.scraper["platforms"]
    assert config.scraper["platforms"]["linkedin"]["enabled"] is True


def test_app_config_migrates_legacy_scraper_to_platforms():
    config = AppConfig(scraper={"headless": False, "scroll_count": 3})

    linkedin = config.scraper["platforms"]["linkedin"]
    assert linkedin["headless"] is False
    assert linkedin["scroll_count"] == 3
    assert linkedin["enabled"] is True


def test_load_config_migrates_legacy_scraper_to_platforms(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        yaml.dump({
            "scraper": {
                "headless": False,
                "scroll_count": 2,
            }
        })
    )

    config = load_config(str(config_file))
    linkedin = config.scraper["platforms"]["linkedin"]

    assert linkedin["headless"] is False
    assert linkedin["scroll_count"] == 2
    assert linkedin["enabled"] is True


def test_load_config_supports_reddit_platform_credentials(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        yaml.dump({
            "scraper": {
                "platforms": {
                    "reddit": {
                        "enabled": True,
                        "client_id": "$NC_REDDIT_CLIENT_ID",
                        "client_secret": "$NC_REDDIT_CLIENT_SECRET",
                        "username": "$NC_REDDIT_USERNAME",
                        "password": "$NC_REDDIT_PASSWORD",
                    }
                }
            }
        })
    )

    config = load_config(str(config_file))
    reddit = config.scraper["platforms"]["reddit"]

    assert reddit["enabled"] is True
    assert reddit["client_id"] == "$NC_REDDIT_CLIENT_ID"
    assert reddit["client_secret"] == "$NC_REDDIT_CLIENT_SECRET"  # noqa: S105
    assert reddit["username"] == "$NC_REDDIT_USERNAME"
    assert reddit["password"] == "$NC_REDDIT_PASSWORD"  # noqa: S105


def test_default_scraper_config_has_rss_platform():
    config = AppConfig()

    assert "rss" in config.scraper["platforms"]
    rss = config.scraper["platforms"]["rss"]
    assert rss["enabled"] is False
    assert rss["feeds"] == []


def test_load_config_supports_rss_feed_list(tmp_path: Path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        yaml.dump({
            "scraper": {
                "platforms": {
                    "rss": {
                        "enabled": True,
                        "feeds": [
                            {"url": "https://example.com/feed.xml", "name": "Example Feed"},
                            {"url": "https://another.example.com/rss", "name": "Another Feed"},
                        ],
                    }
                }
            }
        })
    )

    config = load_config(str(config_file))
    rss = config.scraper["platforms"]["rss"]

    assert rss["enabled"] is True
    assert rss["feeds"] == [
        {"url": "https://example.com/feed.xml", "name": "Example Feed"},
        {"url": "https://another.example.com/rss", "name": "Another Feed"},
    ]
