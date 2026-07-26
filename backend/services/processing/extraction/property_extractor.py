"""PropertyExtractor — address, cadastral number, area."""
from __future__ import annotations

import re

from backend.services.processing.extraction import PropertySection, ExtractedField
from backend.services.processing.extraction.helpers import find_value, parse_money


def extract_property(raw_text: str) -> PropertySection:
    """Extract property details from contract."""
    # Locate "Предмет договора" section
    prop_section = _locate_property_section(raw_text)
    ctx = raw_text[prop_section[0]:prop_section[1]] if prop_section else raw_text[:3000]

    # Address — after "по адресу:"
    address = find_value(ctx, [
        r"(?im)по\s*адресу[:\s]+([^,]+,\s*[^,]+(?:,\s*[^,]+){2,5})",
        r"(?im)адрес[:\s]+(.+?)(?:\s*\.\s*\d|$)",
    ])

    # Area — search for "площадь" pattern
    area = find_value(ctx, [
        r"(?im)площадь\s+([\d]+(?:[.,]\d+)?)\s*кв\.?\s*м",
        r"(?im)([\d]+(?:[.,]\d+)?)\s*кв\.?\s*м",
    ])

    # Cadastral number
    cad_num = find_value(ctx, [
        r"(?im)кадастровый\s*номер\s+(\d{2}:\d{2}:\d{7}:\d+)",
        r"(?im)(\d{2}:\d{2}:\d{4,7}:\d+)",
    ])

    # Floor
    floor = find_value(ctx, [
        r"(?im)этаж\s*№?\s*(\d+)",
    ])

    # Property type
    ptype = find_value(ctx, [
        r"(?im)назначение[:\s]+([^\.]+)",
    ])

    return PropertySection(
        address=ExtractedField(value=address.strip(), confidence=0.85, raw=address) if address else None,
        area_sqm=ExtractedField(value=float(area.replace(",", ".")), confidence=0.9, raw=area) if area else None,
        floor=ExtractedField(value=int(floor), confidence=0.85, raw=floor) if floor else None,
        cadastral_number=ExtractedField(value=cad_num.strip(), confidence=0.95, raw=cad_num) if cad_num else None,
        property_type=ExtractedField(value=ptype.strip(), confidence=0.7, raw=ptype) if ptype else None,
    )


def _locate_property_section(raw_text: str) -> tuple[int, int] | None:
    """Find "Предмет договора" section."""
    m = re.search(r"(?im)^1\.\s*Предмет\s*договора", raw_text)
    if not m:
        m = re.search(r"(?im)Предмет\s*договора", raw_text)
    if not m:
        return None
    start = m.start()
    rest = raw_text[start + 100:start + 2000]
    end_m = re.search(r"(?im)^2\.\s+[А-Я]", rest)
    end = start + 100 + end_m.start() if end_m else min(start + 2000, len(raw_text))
    return (start, end)
