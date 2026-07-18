"""
CanonicalAgreement — canonical agreement representation.

Immutable. NO business logic. Placeholder for phase A3.x.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from domain.business_relationship.agreement_types import AgreementType


@dataclass(frozen=True)
class CanonicalAgreement:
    """Каноническое соглашение. Immutable."""
    id: str = ""
    agreement_id: str = ""
    agreement_type: AgreementType = AgreementType.UNKNOWN
    number: str = ""
    date: str = ""
    amount: Decimal = Decimal("0")
    participant_entity_ids: tuple[str, ...] = ()

    @property
    def confidence(self) -> float:
        return 0.0  # placeholder

    def confirm(self, document_id: str):
        """Placeholder for A3.2. Does nothing on immutable stub."""
