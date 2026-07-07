"""
KnowledgeConflict — description of a knowledge conflict.

Immutable. NO resolution. NO resolution logic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from domain.business_relationship.ke_enums import ConflictType


@dataclass(frozen=True)
class KnowledgeConflict:
    """Описание конфликта знаний. Immutable. Без разрешения."""
    conflict_type: ConflictType
    entity_id: str
    conflicting_sources: tuple[str, ...] = ()
    detected_at: datetime | None = None
    description: str = ""
