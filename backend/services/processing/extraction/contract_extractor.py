"""ContractExtractor — aggregates all section extractors."""
from __future__ import annotations

import time

from backend.services.processing.extraction import (
    ContractProfile, ExtractionMetadata, Severity,
)
from backend.services.processing.extraction.identification_extractor import extract_identification
from backend.services.processing.extraction.party_extractor import extract_parties
from backend.services.processing.extraction.financial_terms_extractor import extract_financial_terms
from backend.services.processing.extraction.property_extractor import extract_property
from backend.services.processing.extraction.date_extractor import extract_dates
from backend.services.processing.extraction.reference_extractor import extract_references
from backend.services.processing.extraction.validators import validate_profile
from backend.services.processing.extraction.helpers import normalize_text


def extract_contract_profile(raw_text: str) -> ContractProfile:
    """Extract structured contract profile from OCR text.

    Each section is extracted independently.
    Profile is validated after extraction.
    """
    start = time.perf_counter()
    text = normalize_text(raw_text)

    profile = ContractProfile(
        identification=extract_identification(text),
        parties=extract_parties(text),
        financial_terms=extract_financial_terms(text),
        prop=extract_property(text),
        dates=extract_dates(text),
        references=extract_references(text),
        metadata=ExtractionMetadata(
            extracted_by="pipeline:extraction-v2",
        ),
    )

    # Validate
    validate_profile(profile)

    # Build confidence per field
    profile.metadata.confidence_per_field = _build_conf_map(profile)
    profile.metadata.extraction_time_ms = int((time.perf_counter() - start) * 1000)

    return profile


def _build_conf_map(profile: ContractProfile) -> dict[str, float]:
    """Build flat confidence dict from all sections."""
    conf = {}
    ident = profile.identification
    for name, field in [("contract_number", ident.contract_number), ("contract_date", ident.contract_date)]:
        if field: conf[name] = field.confidence

    for side in ("seller", "buyer"):
        p = getattr(profile.parties, side)
        for name, field in [("name", p.name), ("inn", p.inn), ("kpp", p.kpp)]:
            if field: conf[f"{side}.{name}"] = field.confidence

    ft = profile.financial_terms
    for name, field in [("total_price", ft.total_price), ("vat_amount", ft.vat_amount)]:
        if field: conf[f"financial.{name}"] = field.confidence

    prop = profile.prop
    for name, field in [("cadastral_number", prop.cadastral_number), ("area", prop.area_sqm), ("address", prop.address)]:
        if field: conf[f"property.{name}"] = field.confidence

    return conf
