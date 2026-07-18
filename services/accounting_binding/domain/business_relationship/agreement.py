"""
Agreement — immutable domain aggregate.

NOT a Document entity. Agreement is inferred from neutral facts.
Immutable. Serializable. Hashable. Technology-independent.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from domain.business_relationship.agreement_types import AgreementType
from domain.business_relationship.agreement_id import AgreementId
from domain.business_relationship.agreement_status import AgreementStatus
from domain.business_relationship.agreement_period import AgreementPeriod
from domain.business_relationship.agreement_participant import AgreementParticipant
from domain.business_relationship.agreement_reference import AgreementReference, ReferenceKind
from domain.business_relationship.agreement_metadata import AgreementMetadata


@dataclass(frozen=True)
class Agreement:
    """Соглашение — каноническое описание бизнес-отношения.

    Immutable. Не содержит выводов.
    Не знает о Knowledge, Graph, Revision, Projection, Query.
    """
    agreement_type: AgreementType
    id: AgreementId
    number: str = ""
    date: date | None = None
    amount: Decimal = Decimal("0")
    currency: str = "RUB"
    status: AgreementStatus = AgreementStatus.DRAFT
    period: AgreementPeriod = field(default_factory=AgreementPeriod)
    participants: tuple[AgreementParticipant, ...] = ()
    references: tuple[AgreementReference, ...] = ()
    metadata: AgreementMetadata = field(default_factory=AgreementMetadata)

    @property
    def participant_count(self) -> int:
        return len(self.participants)

    @property
    def summary(self) -> str:
        return f"{self.agreement_type.value}#{self.number or str(self.id)[:8]}"

    def __repr__(self) -> str:
        return (
            f"Agreement(type={self.agreement_type.value}, "
            f"id={self.id}, "
            f"number={self.number or '-'}, "
            f"participants={self.participant_count}, "
            f"status={self.status.value})"
        )
