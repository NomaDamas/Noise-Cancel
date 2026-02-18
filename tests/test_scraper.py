from __future__ import annotations

import os
import time
from pathlib import Path

import cryptography.fernet
import pytest

from noise_cancel.models import Post


# ---------------------------------------------------------------------------
# auth module tests
# ---------------------------------------------------------------------------
class TestGenerateKey:
    def test_returns_valid_fernet_key(self):
        from cryptography.fernet import Fernet

        from noise_cancel.scraper.auth import generate_key

        key = generate_key()
        # Should not raise
        Fernet(key)

    def test_returns_string(self):
        from noise_cancel.scraper.auth import generate_key

        key = generate_key()
        assert isinstance(key, str)

    def test_keys_are_unique(self):
        from noise_cancel.scraper.auth import generate_key

        keys = {generate_key() for _ in range(10)}
        assert len(keys) == 10


class TestEncryptDecryptSession:
    def test_round_trip(self):
        from noise_cancel.scraper.auth import decrypt_session, encrypt_session, generate_key

        key = generate_key()
        state = {"cookies": [{"name": "li_at", "value": "abc123"}]}
        encrypted = encrypt_session(state, key)
        assert isinstance(encrypted, bytes)
        decrypted = decrypt_session(encrypted, key)
        assert decrypted == state

    def test_wrong_key_fails(self):
        from noise_cancel.scraper.auth import decrypt_session, encrypt_session, generate_key

        key1 = generate_key()
        key2 = generate_key()
        state = {"cookies": []}
        encrypted = encrypt_session(state, key1)
        with pytest.raises(cryptography.fernet.InvalidToken):
            decrypt_session(encrypted, key2)

    def test_encrypted_not_plaintext(self):
        from noise_cancel.scraper.auth import encrypt_session, generate_key

        key = generate_key()
        state = {"secret": "my_token_value"}
        encrypted = encrypt_session(state, key)
        assert b"my_token_value" not in encrypted


class TestSaveLoadSession:
    def test_save_and_load(self, tmp_path):
        from noise_cancel.scraper.auth import generate_key, load_session, save_session

        key = generate_key()
        session_path = str(tmp_path / "session.enc")
        state = {"cookies": [{"name": "li_at", "value": "xyz"}]}
        save_session(state, key, session_path)
        loaded = load_session(key, session_path)
        assert loaded == state

    def test_load_missing_file_returns_none(self, tmp_path):
        from noise_cancel.scraper.auth import generate_key, load_session

        key = generate_key()
        result = load_session(key, str(tmp_path / "nonexistent.enc"))
        assert result is None

    def test_file_created_on_save(self, tmp_path):
        from noise_cancel.scraper.auth import generate_key, save_session

        key = generate_key()
        session_path = str(tmp_path / "session.enc")
        save_session({"data": 1}, key, session_path)
        assert Path(session_path).exists()


class TestIsSessionValid:
    def test_missing_file_is_invalid(self, tmp_path):
        from noise_cancel.scraper.auth import is_session_valid

        assert is_session_valid(str(tmp_path / "nope.enc"), ttl_days=7) is False

    def test_fresh_file_is_valid(self, tmp_path):
        from noise_cancel.scraper.auth import generate_key, is_session_valid, save_session

        key = generate_key()
        session_path = str(tmp_path / "session.enc")
        save_session({"cookies": []}, key, session_path)
        assert is_session_valid(session_path, ttl_days=7) is True

    def test_expired_file_is_invalid(self, tmp_path):
        from noise_cancel.scraper.auth import generate_key, is_session_valid, save_session

        key = generate_key()
        session_path = str(tmp_path / "session.enc")
        save_session({"cookies": []}, key, session_path)
        # Backdate the file mtime by 8 days
        old_time = time.time() - (8 * 86400)
        os.utime(session_path, (old_time, old_time))
        assert is_session_valid(session_path, ttl_days=7) is False

    def test_ttl_boundary(self, tmp_path):
        from noise_cancel.scraper.auth import generate_key, is_session_valid, save_session

        key = generate_key()
        session_path = str(tmp_path / "session.enc")
        save_session({"cookies": []}, key, session_path)
        # Backdate by 6 days (within 7-day TTL)
        old_time = time.time() - (6 * 86400)
        os.utime(session_path, (old_time, old_time))
        assert is_session_valid(session_path, ttl_days=7) is True


# ---------------------------------------------------------------------------
# anti_detection module tests
# ---------------------------------------------------------------------------
class TestRandomDelay:
    def test_within_range(self):
        from noise_cancel.scraper.anti_detection import random_delay

        for _ in range(100):
            val = random_delay(1.0, 3.0)
            assert 1.0 <= val <= 3.0

    def test_custom_range(self):
        from noise_cancel.scraper.anti_detection import random_delay

        for _ in range(100):
            val = random_delay(0.5, 0.6)
            assert 0.5 <= val <= 0.6

    def test_returns_float(self):
        from noise_cancel.scraper.anti_detection import random_delay

        assert isinstance(random_delay(), float)


class TestHumanScrollSequence:
    def test_returns_correct_count(self):
        from noise_cancel.scraper.anti_detection import human_scroll_sequence

        seq = human_scroll_sequence(20)
        assert len(seq) == 20

    def test_dict_structure(self):
        from noise_cancel.scraper.anti_detection import human_scroll_sequence

        seq = human_scroll_sequence(5)
        for action in seq:
            assert "scroll_y" in action
            assert "delay" in action
            assert "direction" in action
            assert action["direction"] in ("down", "up")
            assert isinstance(action["scroll_y"], int)
            assert isinstance(action["delay"], float)

    def test_mostly_down_scrolls(self):
        from noise_cancel.scraper.anti_detection import human_scroll_sequence

        # With 200 scrolls, statistically there should be both up and down
        seq = human_scroll_sequence(200)
        downs = sum(1 for a in seq if a["direction"] == "down")
        ups = sum(1 for a in seq if a["direction"] == "up")
        # 80-90% down, 10-20% up
        assert downs > ups
        assert ups >= 1  # at least some up scrolls with 200 actions

    def test_scroll_y_positive(self):
        from noise_cancel.scraper.anti_detection import human_scroll_sequence

        seq = human_scroll_sequence(10)
        for action in seq:
            assert action["scroll_y"] > 0

    def test_zero_count(self):
        from noise_cancel.scraper.anti_detection import human_scroll_sequence

        seq = human_scroll_sequence(0)
        assert seq == []


class TestRandomViewport:
    def test_returns_dict_with_keys(self):
        from noise_cancel.scraper.anti_detection import random_viewport

        vp = random_viewport()
        assert "width" in vp
        assert "height" in vp
        assert isinstance(vp["width"], int)
        assert isinstance(vp["height"], int)

    def test_realistic_dimensions(self):
        from noise_cancel.scraper.anti_detection import random_viewport

        for _ in range(50):
            vp = random_viewport()
            assert 1024 <= vp["width"] <= 2560
            assert 600 <= vp["height"] <= 1600

    def test_some_variation(self):
        from noise_cancel.scraper.anti_detection import random_viewport

        viewports = [random_viewport() for _ in range(50)]
        widths = {v["width"] for v in viewports}
        # There should be some variation
        assert len(widths) > 1


# ---------------------------------------------------------------------------
# base module tests
# ---------------------------------------------------------------------------
class TestAbstractScraper:
    def test_cannot_instantiate_directly(self):
        from noise_cancel.scraper.base import AbstractScraper

        with pytest.raises(TypeError):
            AbstractScraper()

    def test_subclass_must_implement_methods(self):
        from noise_cancel.scraper.base import AbstractScraper

        class IncompleteScraper(AbstractScraper):
            pass

        with pytest.raises(TypeError):
            IncompleteScraper()

    def test_complete_subclass_works(self):
        from noise_cancel.scraper.base import AbstractScraper

        class CompleteScraper(AbstractScraper):
            async def login(self, headed: bool = True) -> None:
                pass

            async def scrape_feed(self, scroll_count: int = 10) -> list[Post]:
                return []

            async def close(self) -> None:
                pass

        scraper = CompleteScraper()
        assert scraper is not None


# ---------------------------------------------------------------------------
# linkedin module tests
# ---------------------------------------------------------------------------
class TestLinkedInScraperInit:
    def test_init_stores_config(self, app_config):
        from noise_cancel.scraper.linkedin import LinkedInScraper

        scraper = LinkedInScraper(app_config)
        assert scraper.config is app_config

    def test_is_abstract_scraper_subclass(self, app_config):
        from noise_cancel.scraper.base import AbstractScraper
        from noise_cancel.scraper.linkedin import LinkedInScraper

        scraper = LinkedInScraper(app_config)
        assert isinstance(scraper, AbstractScraper)


class TestParsePostElement:
    def test_basic_parse(self, app_config):
        from noise_cancel.scraper.linkedin import LinkedInScraper

        scraper = LinkedInScraper(app_config)
        raw = {
            "id": "post-123",
            "author_name": "Jane Doe",
            "author_url": "https://linkedin.com/in/janedoe",
            "post_url": "https://linkedin.com/feed/update/urn:li:activity:123",
            "post_text": "Great insights on AI!",
            "media_type": "image",
            "likes_count": 42,
            "comments_count": 5,
            "shares_count": 3,
            "post_timestamp": "2025-01-15T10:00:00Z",
        }
        post = scraper.parse_post_element(raw)
        assert isinstance(post, Post)
        assert post.id == "post-123"
        assert post.author_name == "Jane Doe"
        assert post.post_text == "Great insights on AI!"
        assert post.likes_count == 42
        assert post.platform == "linkedin"

    def test_minimal_fields(self, app_config):
        from noise_cancel.scraper.linkedin import LinkedInScraper

        scraper = LinkedInScraper(app_config)
        raw = {
            "id": "post-456",
            "author_name": "John Smith",
            "post_text": "Hello world",
        }
        post = scraper.parse_post_element(raw)
        assert post.id == "post-456"
        assert post.author_name == "John Smith"
        assert post.post_text == "Hello world"
        assert post.likes_count == 0
        assert post.comments_count == 0
        assert post.author_url is None
        assert post.platform == "linkedin"

    def test_parse_preserves_all_fields(self, app_config):
        from noise_cancel.scraper.linkedin import LinkedInScraper

        scraper = LinkedInScraper(app_config)
        raw = {
            "id": "post-789",
            "author_name": "Alice",
            "author_url": "https://linkedin.com/in/alice",
            "post_url": "https://linkedin.com/feed/update/urn:li:activity:789",
            "post_text": "Check this out",
            "media_type": "video",
            "likes_count": 100,
            "comments_count": 20,
            "shares_count": 10,
            "post_timestamp": "2025-03-01T12:00:00Z",
        }
        post = scraper.parse_post_element(raw)
        assert post.author_url == "https://linkedin.com/in/alice"
        assert post.post_url == "https://linkedin.com/feed/update/urn:li:activity:789"
        assert post.media_type == "video"
        assert post.shares_count == 10
        assert post.post_timestamp == "2025-03-01T12:00:00Z"


class TestLinkedInScraperStubs:
    @pytest.mark.anyio
    async def test_login_stub(self, app_config):
        from noise_cancel.scraper.linkedin import LinkedInScraper

        scraper = LinkedInScraper(app_config)
        await scraper.login(headed=False)
        assert scraper._headed is False

    @pytest.mark.anyio
    async def test_scrape_feed_stub(self, app_config):
        from noise_cancel.scraper.linkedin import LinkedInScraper

        scraper = LinkedInScraper(app_config)
        result = await scraper.scrape_feed(scroll_count=5)
        assert result == []

    @pytest.mark.anyio
    async def test_close_stub(self, app_config):
        from noise_cancel.scraper.linkedin import LinkedInScraper

        scraper = LinkedInScraper(app_config)
        # Should not raise
        await scraper.close()
