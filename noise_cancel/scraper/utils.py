"""Shared utilities for scraper modules."""

from __future__ import annotations


def clean_str(value: object) -> str:
    """Strip whitespace from a string."""
    if value is None:
        return ""
    return str(value).strip()


def optional_clean_str(value: object) -> str | None:
    """Strip whitespace if value is not None/empty, else return None."""
    if not value:
        return None
    cleaned = str(value).strip()
    return cleaned if cleaned else None
