"""
AgreementParticipant — role of an entity in an agreement.

Immutable. Each participant has a role, share, and time range.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from domain.business_relationship.agreement_types import ParticipantRole
from domain.business_relationship.agreement_id import AgreementId
from domain.business_relationship.agreement_period import AgreementPeriod


@dataclass(frozen=True)
class AgreementParticipant:
    """Участник соглашения с ролью. Immutable."""
    agreement_id: AgreementId
    entity_id: str
    participant_role: ParticipantRole
    share: Decimal | None = None
    period: AgreementPeriod = field(default_factory=AgreementPeriod)
    confidence: float = 1.0
