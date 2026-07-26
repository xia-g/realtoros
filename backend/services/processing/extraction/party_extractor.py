"""PartyExtractor — seller/buyer from normalized contract text."""
from __future__ import annotations

import re

from backend.services.processing.extraction import PartiesSection, Party, ExtractedField, PartyType
from backend.services.processing.extraction.helpers import find_value


def extract_parties(raw_text: str) -> PartiesSection:
    """Extract seller and buyer parties from contract text."""
    text_lower = raw_text.lower()

    seller_name = _find_entity(raw_text, "Продавец")
    seller_inn = find_value(raw_text, [r"(?im)инн\s*(\d{10,12})"])
    seller_kpp = find_value(raw_text, [r"(?im)кпп\s*(\d{9})"])
    buyer_name = _find_entity(raw_text, "Покупатель")
    buyer_inn = find_value(raw_text[2000:5000], [r"(?im)инн\s*(\d{10,12})"])

    seller = Party(
        name=ExtractedField(value=seller_name.strip(), confidence=0.85, raw=seller_name) if seller_name else None,
        party_type=ExtractedField(value=PartyType.LEGAL.value, confidence=0.8) if seller_name and ("комитет" in seller_name.lower() or "ооо" in seller_name.lower()) else None,
        inn=ExtractedField(value=seller_inn, confidence=0.9, raw=seller_inn) if seller_inn else None,
        kpp=ExtractedField(value=seller_kpp, confidence=0.9, raw=seller_kpp) if seller_kpp else None,
    )

    buyer = Party(
        name=ExtractedField(value=buyer_name.strip(), confidence=0.85, raw=buyer_name) if buyer_name else None,
        party_type=ExtractedField(value=PartyType.INDIVIDUAL.value, confidence=0.9) if buyer_name and len(buyer_name.split()) in (2, 3) else None,
        inn=ExtractedField(value=buyer_inn, confidence=0.9, raw=buyer_inn) if buyer_inn else None,
    )

    return PartiesSection(seller=seller, buyer=buyer)


def _find_entity(raw_text: str, role: str) -> str | None:
    """Find entity name by role (Продавец/Покупатель).

    Seller is searched in first 2000 chars, buyer in the rest.
    """
    zone = raw_text[:2000] if role == "Продавец" else raw_text[1000:4000]

    # 1. Entity before "именуемый в дальнейшем «ROLE»"
    m = re.search(
        rf"([А-ЯЁ][А-ЯЁ ]{{4,60}}),\s*именуем[а-я]+\s+в\s+дальнейшем\s+«{role}»",
        zone,
    )
    if m:
        name = m.group(1).strip().rstrip(",")
        if len(name) > 5:
            return name

    # 2. For Покупатель: name before "именуемая в дальнейшем «Покупатель»"
    if role == "Покупатель":
        m = re.search(
            r"([А-Я][а-я]+ [А-Я][а-я]+ [А-Я][а-я]+),\s*именуем[а-я]+\s+в\s+дальнейшем\s+«Покупатель»",
            zone,
        )
        if m:
            return m.group(1).strip()

    # 3. Look for "Комитет" or similar in header area (for seller)
    if role == "Продавец":
        common = re.search(r"(Комитет[^,]+)", raw_text[:1500])
        if common:
            return common.group(1).strip()

    return None
