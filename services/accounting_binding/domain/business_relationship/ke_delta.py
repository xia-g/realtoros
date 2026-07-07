"""
KnowledgeDelta — set of changes for one entity triggered by one event.

Immutable. NO execution. NO merge. Just description of changes.
"""
from __future__ import annotations

from dataclasses import dataclass

from domain.business_relationship.ke_identifiers import KnowledgeEventId
from domain.business_relationship.ke_change import KnowledgeChange


@dataclass(frozen=True)
class KnowledgeDelta:
    """Дельта изменений для одной сущности. Immutable."""
    entity_id: str
    event_id: KnowledgeEventId
    changes: tuple[KnowledgeChange, ...] = ()
