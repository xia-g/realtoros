"""
KnowledgeEvent — immutable domain event for the knowledge layer.

NO methods that apply, resolve, execute, or calculate.
All events are append-only descriptions.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from domain.business_relationship.ke_identifiers import KnowledgeEventId
from domain.business_relationship.ke_enums import KnowledgeEventType, TrustLevel, AuthorityLevel


@dataclass(frozen=True)
class KnowledgeEvent:
    """Событие изменения знания. Immutable. Без логики."""
    event_id: KnowledgeEventId
    event_type: KnowledgeEventType
    entity_id: str
    agreement_id: str = ""
    occurred_at: datetime | None = None
    trust_level: TrustLevel = TrustLevel.UNKNOWN
    authority_level: AuthorityLevel = AuthorityLevel.UNKNOWN
    description: str = ""
