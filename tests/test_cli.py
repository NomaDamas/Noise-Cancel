from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from typer.testing import CliRunner

from noise_cancel.cli import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_config(tmp_path: Path) -> tuple[Path, Path]:
    """Write a minimal config YAML and return (config_path, data_dir)."""
    data_dir = tmp_path / "data"
    config_path = tmp_path / "config.yaml"
    config_path.write_text(f"general:\n  data_dir: {data_dir}\n")
    return config_path, data_dir


def _mock_scraper(storage_state: dict | None = None) -> MagicMock:
    """Create a mock LinkedInScraper instance with the given storage state."""
    mock = MagicMock()
    mock.login = AsyncMock()
    mock.storage_state = storage_state
    return mock


def test_app_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "noise-cancel" in result.output.lower() or "Usage" in result.output


def test_config_command():
    result = runner.invoke(app, ["config"])
    assert result.exit_code == 0


def test_init_creates_config(tmp_path: Path):
    out = tmp_path / "config.yaml"
    result = runner.invoke(app, ["init", "--config", str(out)])
    assert result.exit_code == 0
    assert out.exists()
    content = out.read_text()
    assert "classifier:" in content
    assert "claude-sonnet-4-6" in content
    assert "Read" in content
    assert "Skip" in content


def test_init_refuses_overwrite(tmp_path: Path):
    out = tmp_path / "config.yaml"
    out.write_text("existing")
    result = runner.invoke(app, ["init", "--config", str(out)])
    assert result.exit_code == 1
    assert "already exists" in result.output
    # Original content preserved
    assert out.read_text() == "existing"


# ===========================================================================
# Login command tests
# ===========================================================================


class TestLoginCommand:
    def test_login_saves_session_and_key(self, tmp_path: Path):
        config_path, data_dir = _write_config(tmp_path)
        mock_storage = {"cookies": [{"name": "li_at", "value": "abc123"}]}
        mock = _mock_scraper(storage_state=mock_storage)

        with patch("noise_cancel.scraper.linkedin.LinkedInScraper", return_value=mock):
            result = runner.invoke(app, ["login", "--config", str(config_path)])

        assert result.exit_code == 0
        assert "Login successful" in result.output
        assert (data_dir / "session.enc").exists()
        assert (data_dir / "session.key").exists()

    def test_login_session_is_decryptable(self, tmp_path: Path):
        from noise_cancel.scraper.auth import load_session

        config_path, data_dir = _write_config(tmp_path)
        mock_storage = {"cookies": [{"name": "li_at", "value": "secret"}]}
        mock = _mock_scraper(storage_state=mock_storage)

        with patch("noise_cancel.scraper.linkedin.LinkedInScraper", return_value=mock):
            runner.invoke(app, ["login", "--config", str(config_path)])

        key = (data_dir / "session.key").read_text().strip()
        loaded = load_session(key, str(data_dir / "session.enc"))
        assert loaded == mock_storage

    def test_login_reuses_existing_key(self, tmp_path: Path):
        from noise_cancel.scraper.auth import generate_key

        config_path, data_dir = _write_config(tmp_path)
        data_dir.mkdir(parents=True, exist_ok=True)
        existing_key = generate_key()
        (data_dir / "session.key").write_text(existing_key)

        mock = _mock_scraper(storage_state={"cookies": []})

        with patch("noise_cancel.scraper.linkedin.LinkedInScraper", return_value=mock):
            result = runner.invoke(app, ["login", "--config", str(config_path)])

        assert result.exit_code == 0
        # Key file should still contain the original key
        assert (data_dir / "session.key").read_text().strip() == existing_key

    def test_login_fails_when_no_session_captured(self, tmp_path: Path):
        config_path, _ = _write_config(tmp_path)
        mock = _mock_scraper(storage_state=None)

        with patch("noise_cancel.scraper.linkedin.LinkedInScraper", return_value=mock):
            result = runner.invoke(app, ["login", "--config", str(config_path)])

        assert result.exit_code == 1
        assert "Login failed" in result.output

    def test_login_key_file_permissions(self, tmp_path: Path):
        config_path, data_dir = _write_config(tmp_path)
        mock = _mock_scraper(storage_state={"cookies": []})

        with patch("noise_cancel.scraper.linkedin.LinkedInScraper", return_value=mock):
            runner.invoke(app, ["login", "--config", str(config_path)])

        key_stat = (data_dir / "session.key").stat()
        # Owner read/write only (0o600)
        assert oct(key_stat.st_mode)[-3:] == "600"
