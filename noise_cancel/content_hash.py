from __future__ import annotations

import hashlib


def normalize_post_text(post_text: str) -> str:
    """Normalize post text for deduplication."""
    return "".join(post_text.split()).lower()


def compute_content_hash(post_text: str) -> str:
    """Compute SHA-256 hash of normalized post text."""
    normalized = normalize_post_text(post_text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
