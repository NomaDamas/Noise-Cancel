from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from noise_cancel.scraper.linkedin import LinkedInScraper
from noise_cancel.scraper.threads import ThreadsScraper
from noise_cancel.scraper.x import XScraper


def _write_session_file(path: Path, *, now: float, age_hours: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("encrypted-session")
    mtime = now - (age_hours * 3600)
    os.utime(path, (mtime, mtime))


def test_x_session_age_and_expiry_days_are_calculated(app_config) -> None:
    app_config.scraper["platforms"]["x"] = {"enabled": True, "session_ttl_days": 1}
    scraper = XScraper(app_config)

    now = 2_000_000_000.0
    session_path = Path(app_config.general["data_dir"]) / "x_session.enc"
    _write_session_file(session_path, now=now, age_hours=12)

    with patch("noise_cancel.scraper.auth.time.time", return_value=now):
        assert scraper.session_age_days() == pytest.approx(0.5)
        assert scraper.session_expires_in_days() == pytest.approx(0.5)


def test_threads_session_age_and_expiry_days_are_calculated(app_config) -> None:
    app_config.scraper["platforms"]["threads"] = {"enabled": True, "session_ttl_days": 2}
    scraper = ThreadsScraper(app_config)

    now = 2_000_000_000.0
    session_path = Path(app_config.general["data_dir"]) / "threads_session.enc"
    _write_session_file(session_path, now=now, age_hours=6)

    with patch("noise_cancel.scraper.auth.time.time", return_value=now):
        assert scraper.session_age_days() == pytest.approx(0.25)
        assert scraper.session_expires_in_days() == pytest.approx(1.75)


def test_linkedin_session_age_and_expiry_days_are_calculated(app_config) -> None:
    app_config.scraper["platforms"]["linkedin"]["session_ttl_days"] = 2
    scraper = LinkedInScraper(app_config)

    now = 2_000_000_000.0
    session_path = Path(app_config.general["data_dir"]) / "session.enc"
    _write_session_file(session_path, now=now, age_hours=24)

    with patch("noise_cancel.scraper.auth.time.time", return_value=now):
        assert scraper.session_age_days() == pytest.approx(1.0)
        assert scraper.session_expires_in_days() == pytest.approx(1.0)


def test_session_age_methods_return_none_when_no_session_file(app_config) -> None:
    scraper = XScraper(app_config)
    assert scraper.session_age_days() is None
    assert scraper.session_expires_in_days() is None
