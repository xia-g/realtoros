"""
AgreementCandidate — possible agreement derived from facts.

Immutable. Produced by AgreementInterpreter.
Not yet matched against existing agreements.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from domain.business_relationship.agreement_types import AgreementType, ParticipantRole
from domain.business_relationship.fact import BusinessFact


@dataclass(frozen=True)
class AgreementCandidate:
    """Кандидат на соглашение. Ещё не проверен на существующие."""
    agreement_type: AgreementType
    contract_number: str
    amount: Decimal = Decimal("0")
    participant_roles: tuple[tuple[str, ParticipantRole], ...] = ()
    supporting_document_ids: tuple[str, ...] = ()
    confidence: float = 0.0
    source_facts: tuple[BusinessFact, ...] = ()

    @property
    def participant_count(self) -> int:
        return len(self.participant_roles)

    @property
    def has_minimal_data(self) -> bool:
        return self.agreement_type != AgreementType.UNKNOWN and self.participant_count > 0
