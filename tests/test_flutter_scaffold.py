from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_ROOT = PROJECT_ROOT / "app"


def _exists_any(base: Path, relative_paths: set[str]) -> bool:
    return any((base / relative_path).is_file() for relative_path in relative_paths)


def test_flutter_project_scaffold_and_theme_requirements():
    pubspec_path = APP_ROOT / "pubspec.yaml"
    main_dart_path = APP_ROOT / "lib" / "main.dart"
    app_dart_path = APP_ROOT / "lib" / "app.dart"
    android_dir = APP_ROOT / "android"
    ios_dir = APP_ROOT / "ios"

    assert APP_ROOT.is_dir()
    assert pubspec_path.is_file()
    assert main_dart_path.is_file()
    assert android_dir.is_dir()
    assert ios_dir.is_dir()
    assert _exists_any(
        android_dir,
        {"build.gradle.kts", "build.gradle"},
    )
    assert _exists_any(
        android_dir / "app",
        {"build.gradle.kts", "build.gradle"},
    )
    assert _exists_any(
        android_dir,
        {"settings.gradle.kts", "settings.gradle"},
    )
    assert (android_dir / "gradle" / "wrapper" / "gradle-wrapper.properties").is_file()
    assert _exists_any(
        ios_dir,
        {"Runner.xcodeproj/project.pbxproj"},
    )
    assert _exists_any(
        ios_dir / "Runner",
        {"AppDelegate.swift", "AppDelegate.m"},
    )
    assert (ios_dir / "Runner.xcworkspace" / "contents.xcworkspacedata").is_file()
    assert _exists_any(
        ios_dir / "Flutter",
        {"Debug.xcconfig"},
    )

    pubspec = yaml.safe_load(pubspec_path.read_text())
    dependencies = pubspec.get("dependencies", {})
    required_dependencies = {
        "http",
        "provider",
        "flutter_card_swiper",
        "url_launcher",
        "flutter_secure_storage",
        "google_fonts",
    }
    assert required_dependencies.issubset(set(dependencies))

    theme_source = (app_dart_path if app_dart_path.exists() else main_dart_path).read_text()
    assert "MaterialApp" in theme_source
    assert "ChangeNotifierProvider" in theme_source
    assert "0xFF121212" in theme_source
    assert "0xFF1E1E1E" in theme_source
    assert "Colors.blue" in theme_source or "ColorScheme.fromSeed" in theme_source


def test_gitignore_has_flutter_artifact_patterns():
    gitignore_text = (PROJECT_ROOT / ".gitignore").read_text()
    required_patterns = [
        "app/build/",
        "app/.dart_tool/",
        "app/ios/Pods/",
        "app/.flutter-plugins",
        "app/.flutter-plugins-dependencies",
    ]

    for pattern in required_patterns:
        assert pattern in gitignore_text
