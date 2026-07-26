"""IdentificationExtractor — contract number, date, place."""
from __future__ import annotations

import re

from backend.services.processing.extraction import IdentificationSection, ExtractedField
from backend.services.processing.extraction.helpers import find_value


def extract_identification(raw_text: str) -> IdentificationSection:
    """Extract contract identification from document header."""
    header = raw_text[:1000]
    num = find_value(header, [
        r"(?im)договор\s*№\s*(\S+)",
        r"(?im)№\s*(\S{3,30})",
    ])
    cnum = None
    if num:
        cnum = ExtractedField(value=num.strip(), confidence=0.9, raw=num.strip())

    # Date — look for the signing date in header
    date_val = find_value(header, [
        r"(\d{1,2}\s+(?:мая)\s+\d{4})",
        r"(\d{2}\.\d{2}\.\d{4})",
    ])
    cdate = None
    if date_val:
        # Convert Russian month name to date
        from datetime import datetime
        months = {
            "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
            "мая": 5, "июня": 6, "июля": 7, "августа": 8,
            "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
        }
        try:
            parts = date_val.split()
            if len(parts) == 3 and parts[1].lower() in months:
                dt = datetime(int(parts[2]), months[parts[1].lower()], int(parts[0]))
                cdate = ExtractedField(value=dt.date(), confidence=0.9, raw=date_val)
            elif "." in date_val:
                parts = date_val.split(".")
                if len(parts) == 3:
                    dt = datetime(int(parts[2]), int(parts[1]), int(parts[0]))
                    cdate = ExtractedField(value=dt.date(), confidence=0.9, raw=date_val)
        except (ValueError, IndexError):
            pass

    # Place — find city name (e.g. "Санкт-Петербург" or "Москва")
    place = find_value(header[80:400], [
        r"([А-Я][а-я]+(?:\s[А-Я][а-я]+)*(?:бург|сква|поль|град))",
    ])
    cplace = None
    if place and len(place) > 3:
        cplace = ExtractedField(value=place.strip(), confidence=0.7, raw=place.strip())

    return IdentificationSection(
        contract_number=cnum,
        contract_date=cdate,
        place_of_signing=cplace,
    )
