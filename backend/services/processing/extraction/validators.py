"""Profile validators — structural + semantic checks."""
from __future__ import annotations

from backend.services.processing.extraction import (
    ContractProfile, Severity,
)


REQUIRED = ["contract_number", "contract_date"]


def validate_profile(profile: ContractProfile) -> None:
    """Run all validations. Adds warnings to profile.metadata."""
    _validate_required(profile)
    _validate_financial(profile)


def _validate_required(profile: ContractProfile) -> None:
    """Check that required fields are present."""
    missing = []
    ident = profile.identification
    if not ident.contract_number:
        missing.append("contract_number")
    if not ident.contract_date:
        missing.append("contract_date")

    for field in missing:
        profile.metadata.add_warning(field, "FIELD_NOT_FOUND", f"Required field '{field}' not found", Severity.WARNING)


def _validate_financial(profile: ContractProfile) -> None:
    """Cross-validate financial terms."""
    ft = profile.financial_terms
    if ft.total_price and ft.vat_amount:
        total = ft.total_price.value
        vat = ft.vat_amount.value
        if isinstance(total, (int, float)) and isinstance(vat, (int, float)):
            if vat > total:
                profile.metadata.add_warning(
                    "vat_amount", "CROSS_VALIDATION_FAIL",
                    f"VAT ({vat}) exceeds total price ({total})",
                    Severity.INFO,
                )
