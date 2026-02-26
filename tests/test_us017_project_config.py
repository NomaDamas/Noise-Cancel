from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAKEFILE_PATH = PROJECT_ROOT / "Makefile"
CLAUDE_PATH = PROJECT_ROOT / "CLAUDE.md"
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"


def test_makefile_has_server_target():
    makefile_text = MAKEFILE_PATH.read_text()
    assert "server: ## Start FastAPI dev server" in makefile_text
    assert "uv run uvicorn server.main:app --reload --host 0.0.0.0 --port 8012" in makefile_text


def test_makefile_has_test_server_target():
    makefile_text = MAKEFILE_PATH.read_text()
    assert "test-server: ## Run server tests only" in makefile_text
    assert "uv run python -m pytest tests_server" in makefile_text


def test_makefile_has_flutter_run_target():
    makefile_text = MAKEFILE_PATH.read_text()
    assert "flutter-run: ## Run Flutter app" in makefile_text
    assert "cd app && flutter run" in makefile_text


def test_makefile_test_target_runs_core_and_server_tests():
    makefile_text = MAKEFILE_PATH.read_text()
    assert "uv run python -m pytest --doctest-modules tests tests_server" in makefile_text


def test_claude_documents_monorepo_structure_and_components():
    claude_text = CLAUDE_PATH.read_text()
    required_snippets = [
        "noise_cancel/",
        "server/",
        "app/",
        "tests_server/",
        "FastAPI",
        "Flutter",
        "Tinder-style",
        "swipe",
    ]
    for snippet in required_snippets:
        assert snippet in claude_text


def test_pyproject_pytest_testpaths_include_server_suite():
    pyproject_text = PYPROJECT_PATH.read_text()
    assert 'testpaths = ["tests", "tests_server"]' in pyproject_text
