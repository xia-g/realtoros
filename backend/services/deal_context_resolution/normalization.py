"""Normalization utilities for resolution matching.

Before matching, raw OCR values are normalised to canonical formats
to eliminate false negatives caused by whitespace, dashes, or case mismatches.
"""

from __future__ import annotations


def normalize_inn(value: str | None) -> str | None:
    """Normalize INN: strip whitespace, keep digits only.

    Canonical form: '7701234567' (legal) or '123456789012' (individual).

    Args:
        value: Raw INN string from OCR or user input.

    Returns:
        Digits-only string, or None if input is None.
    """
    if value is None:
        return None
    digits = "".join(ch for ch in value.strip() if ch.isdigit())
    return digits if digits else None


def normalize_cadastral(value: str | None) -> str | None:
    """Normalize cadastral number: replace hyphens/spaces with colons, uppercase.

    Canonical form: '77:01:0004012:123'.

    Args:
        value: Raw cadastral number from OCR (may contain dashes, spaces, mixed case).

    Returns:
        Normalized cadastral string, or None if input is None.
    """
    if value is None:
        return None
    normalized = value.strip().replace("-", ":").replace(" ", ":").upper()
    return normalized if normalized else None
