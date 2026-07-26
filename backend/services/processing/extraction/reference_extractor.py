"""ReferenceExtractor — protocol, tender references."""
from __future__ import annotations

from backend.services.processing.extraction import ReferenceSection, ExtractedField
from backend.services.processing.extraction.helpers import find_value


def extract_references(raw_text: str) -> ReferenceSection:
    """Extract references to related documents."""
    protocol_num = find_value(raw_text, [
        r"(?im)протокола[^.]*?от\s+(\d{2}\.\d{2}\.\d{4})",
        r"(?im)протокол[^№]*№\s*([^\s,]+)",
    ])

    protocol_date = find_value(raw_text, [
        r"(?im)протокола[^.]*?от\s+(\d{2}\.\d{2}\.\d{4})",
    ])

    tender_num = find_value(raw_text, [
        r"(?im)номер\s*извещения[^:]*:\s*(\d+)",
        r"(?im)извещения[^:]*:\s*(\d+)",
    ])

    return ReferenceSection(
        protocol_number=ExtractedField(value=protocol_num.strip(), confidence=0.7, raw=protocol_num) if protocol_num else None,
        protocol_date=ExtractedField(value=protocol_date.strip(), confidence=0.7, raw=protocol_date) if protocol_date else None,
        tender_number=ExtractedField(value=tender_num.strip(), confidence=0.85, raw=tender_num) if tender_num else None,
    )
