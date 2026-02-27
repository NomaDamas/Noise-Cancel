from __future__ import annotations

import hashlib

from noise_cancel.content_hash import compute_content_hash


def test_compute_content_hash_normalizes_whitespace_and_case() -> None:
    value = "  Hello \n\t WORLD  "
    expected = hashlib.sha256(b"helloworld").hexdigest()

    assert compute_content_hash(value) == expected


def test_compute_content_hash_same_text_same_hash() -> None:
    first = "Machine learning is cool"
    second = "  machine   learning\nis\tcool "

    assert compute_content_hash(first) == compute_content_hash(second)
