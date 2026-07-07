"""
KnowledgeTimelineEntry — one entry in a knowledge timeline.

Immutable. No ordering logic.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from domain.business_relationship.ke_identifiers import KnowledgeEventId


@dataclass(frozen=True)
class KnowledgeTimelineEntry:
    """Запись временной шкалы знаний. Immutable."""
    timestamp: datetime
    event_id: KnowledgeEventId
    entity_id: str
    summary: str
