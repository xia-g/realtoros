"""Shared helpers for contract extraction."""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from backend.services.processing.extraction import ExtractedField


def normalize_text(raw_text: str) -> str:
    """Normalize OCR text: newlines → spaces, multiple spaces → single.

    OCRNode returns \n between every word, which breaks multi-word regex.
    """
    text = raw_text.replace("\\n", " ").replace("\n", " ").replace("\r", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def find_section(raw_text: str, *headers: str) -> tuple[int, int] | None:
    """Find section boundaries by header keywords.

    Returns (start, end) char offsets, or (0, 0) if not found.
    """
    lower = raw_text.lower()
    starts = []
    for h in headers:
        # Try with section number first
        for pattern in [
            rf"(?im)^{re.escape(h)}",
            rf"(?im){re.escape(h)}",
        ]:
            m = re.search(pattern, lower)
            if m:
                starts.append(m.start())
                break

    if not starts:
        return (0, 0)

    start = min(starts)
    # End = next section header or end of text
    rest = lower[start + 200:] if len(lower) > start + 200 else ""
    m = re.search(r"(?im)^\d+\.\s+[А-Я]", rest)
    end = start + 200 + m.start() if m else len(raw_text)
    if m:
        end = start + 200 + m.start()

    return (start, end)


def find_value(text: str, patterns: list[str], group: int = 1) -> str | None:
    """Try pattern chain, return first match."""
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            val = m.group(group).strip()
            if val:
                return val
    return None


def parse_money(text: str) -> Decimal | None:
    """Parse Russian money string to Decimal.

    Handles: "18 178 000", "18 178 000,00", "1 817 800 рублей"
    """
    if not text:
        return None
    # Remove spaces, replace comma with dot
    cleaned = re.sub(r"[^0-9,.]", "", text.replace(" ", ""))
    cleaned = cleaned.replace(",", ".")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def extract_number_words(text: str) -> str | None:
    """Extract a number that appears before or after a keyword."""
    # Simple: find first group of digits
    m = re.search(r"(\d[\d\s]*)", text)
    return m.group(1).strip() if m else None


def money_field(value: Any, confidence: float = 1.0) -> ExtractedField | None:
    if value is None:
        return None
    if isinstance(value, str):
        parsed = parse_money(value)
        if parsed is None:
            return ExtractedField(value=value, confidence=confidence * 0.5, raw=value)
        return ExtractedField(value=float(parsed), confidence=confidence, raw=value)
    return ExtractedField(value=float(value), confidence=confidence, raw=str(value))
