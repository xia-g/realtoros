"""FinancialTermsExtractor — prices, VAT, deposit."""
from __future__ import annotations

import re
from decimal import Decimal

from backend.services.processing.extraction import FinancialTermsSection, ExtractedField
from backend.services.processing.extraction.helpers import find_value, parse_money, money_field


def extract_financial_terms(raw_text: str) -> FinancialTermsSection:
    """Extract financial terms from price section."""
    # Locate price section
    price_section = _locate_price_section(raw_text)
    if not price_section:
        return FinancialTermsSection()

    ctx = raw_text[price_section[0]:price_section[1]]

    total_price = _extract_total_price(ctx)
    vat = _extract_vat(ctx)
    deposit = _extract_deposit(ctx)
    remaining = _extract_remaining(ctx)

    # Cross-validation: if we have both price and vat, compute excluded
    excl = None
    if total_price and vat:
        try:
            p = Decimal(str(total_price.value))
            v = Decimal(str(vat.value))
            excl = ExtractedField(value=float(p - v), confidence=min(total_price.confidence, vat.confidence) * 0.95, raw="")
        except Exception:
            pass

    return FinancialTermsSection(
        total_price=total_price,
        vat_amount=vat,
        price_excluding_vat=excl,
        deposit_amount=deposit,
        currency=ExtractedField(value="RUB", confidence=1.0),
    )


def _locate_price_section(raw_text: str) -> tuple[int, int] | None:
    """Find "Цена и порядок расчётов" section."""
    m = re.search(r"(?im)^2\.\s*Цена\s*и\s*порядок\s*расчетов", raw_text)
    if not m:
        m = re.search(r"(?im)Цена\s*продажи", raw_text)
    if not m:
        return None
    start = m.start()
    # End: next section header or 3000 chars
    rest = raw_text[start + 200:start + 3000]
    end_m = re.search(r"(?im)^\d+\.\s+[А-Я]", rest)
    end = start + 200 + end_m.start() if end_m else min(start + 3000, len(raw_text))
    return (start, end)


def _extract_total_price(ctx: str) -> ExtractedField | None:
    m = re.search(
        r"(?im)Цена\s*продажи\s*Объекта\s*составляет\s+([\d\s]+)\s*\([^)]*\)\s*рублей",
        ctx,
    )
    if not m:
        m = re.search(r"(?im)Цена\s*продажи\s*Объекта\s+([\d\s]+)\s*руб", ctx)
    if not m:
        m = re.search(r"(?im)составляет\s+([\d\s]+)\s*рублей", ctx)
    if m:
        val = m.group(1).strip()
        parsed = parse_money(val)
        if parsed:
            return ExtractedField(value=float(parsed), confidence=0.9, raw=val)
    return None


def _extract_vat(ctx: str) -> ExtractedField | None:
    # First look for explicit "НДС составляет" pattern
    m = re.search(
        r"(?im)налог\s+на\s+добавленную\s+стоимость.*?составляет\s+([\d\s]+)\s*\([^)]*\)\s*рублей",
        ctx,
    )
    if not m:
        m = re.search(r"(?im)НДС\s+составляет\s+([\d\s]+)\s*\([^)]*\)\s*рублей", ctx)
    if m:
        val = m.group(1).strip()
        parsed = parse_money(val)
        if parsed:
            return ExtractedField(value=float(parsed), confidence=0.9, raw=val)

    # Fallback: only match standalone "НДС" (not "без учета НДС")
    m = re.search(r"(?im)(?:в\s+том\s+числе|включая)\s+НДС.*?([\d\s]+)\s*руб", ctx)
    if m:
        val = m.group(1).strip()
        parsed = parse_money(val)
        if parsed:
            return ExtractedField(value=float(parsed), confidence=0.8, raw=val)

    return None


def _extract_deposit(ctx: str) -> ExtractedField | None:
    m = re.search(
        r"(?im)задаток\s*в\s*размере\s+([\d\s]+)\s*\([^)]*\)\s*рублей",
        ctx,
    )
    if not m:
        m = re.search(r"(?im)задаток.*?([\d\s]+)\s*руб", ctx)
    if m:
        val = m.group(1).strip()
        parsed = parse_money(val)
        if parsed:
            return ExtractedField(value=float(parsed), confidence=0.85, raw=val)
    return None


def _extract_remaining(ctx: str) -> ExtractedField | None:
    m = re.search(
        r"(?im)оставшаяся\s*часть.*?составляет\s+([\d\s]+)\s*\([^)]*\)\s*рублей",
        ctx,
    )
    if m:
        val = m.group(1).strip()
        parsed = parse_money(val)
        if parsed:
            return ExtractedField(value=float(parsed), confidence=0.85, raw=val)
    return None
