"""DateExtractor — signing, payment, transfer dates."""
from __future__ import annotations

from datetime import datetime

from backend.services.processing.extraction import DatesSection, ExtractedField
from backend.services.processing.extraction.helpers import find_value


MONTHS_RU = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
    "мая": 5, "июня": 6, "июля": 7, "августа": 8,
    "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}


def extract_dates(raw_text: str) -> DatesSection:
    """Extract key dates from contract."""
    # Signing date — from header
    signing = _find_date(raw_text[:2000], [
        r"(?im)Санкт-Петербург\s+(\d{1,2})\s+(мая)\s+(\d{4})",
        r"(?im)(\d{1,2})\s+(мая)\s+(\d{4})\s*г\.",
        r"(?im)(\d{2}\.\d{2}\.\d{4})",
    ])

    # Payment deadline — look in price section
    payment = _find_date(raw_text, [
        r"(?im)не\s*позднее\s+(\d{1,2})\s*[\(]?\s*[д]?\s*дней",
        r"(?im)до\s+(\d{2}\.\d{2}\.\d{4})",
    ])

    # Transfer deadline — look in obligations section
    transfer = _find_date(raw_text, [
        r"(?im)передать\s*[^.]*?в\s*течение\s+(\d+)\s+дней",
    ])

    result = DatesSection()
    if signing:
        result.signing_date = signing
    if payment:
        result.payment_deadline = payment
    if transfer:
        result.transfer_deadline = transfer

    return result


def _find_date(text: str, patterns: list[str]) -> ExtractedField | None:
    """Try to find and parse a date from text."""
    val = find_value(text, patterns, group=0)
    if not val:
        return None

    # Try Russian month name format
    m = __import__("re").search(r"(\d{1,2})\s+([а-я]+)\s+(\d{4})", val)
    if m:
        day, month_name, year = int(m.group(1)), m.group(2).lower(), int(m.group(3))
        if month_name in MONTHS_RU:
            try:
                dt = datetime(year, MONTHS_RU[month_name], day)
                return ExtractedField(value=dt.date(), confidence=0.9, raw=val)
            except ValueError:
                pass

    # Try DD.MM.YYYY
    m = __import__("re").search(r"(\d{2})\.(\d{2})\.(\d{4})", val)
    if m:
        try:
            dt = datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            return ExtractedField(value=dt.date(), confidence=0.9, raw=val)
        except ValueError:
            pass

    return ExtractedField(value=val, confidence=0.5, raw=val)
