"""
AgreementParticipant — role of an entity in an agreement.

NOT list[str]. Each participant has a role, share, and time range.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date

from domain.business_relationship.agreement_types import ParticipantRole


@dataclass
class AgreementParticipant:
    """Участник соглашения с ролью."""
    agreement_id: str
    entity_id: str                            # ссылка на BusinessEntity
    participant_role: ParticipantRole
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    share: float | None = None                # доля (для нескольких участников)
    valid_from: date | None = None
    valid_to: date | None = None
    confidence: float = 0.0
