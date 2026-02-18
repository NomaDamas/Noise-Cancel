from typer.testing import CliRunner

from noise_cancel.cli import app

runner = CliRunner()


def test_app_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "noise-cancel" in result.output.lower() or "Usage" in result.output


def test_config_command():
    result = runner.invoke(app, ["config"])
    assert result.exit_code == 0
