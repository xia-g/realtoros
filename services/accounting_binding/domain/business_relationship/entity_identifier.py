"""
EntityIdentifier — identifier linking a canonical entity to the real world.

Immutable value object. No normalization logic.
The identifier is already resolved — this is pure data.
"""
from __future__ import annotations

from dataclasses import dataclass

from domain.business_relationship.entity_types import IdentifierType


@dataclass(frozen=True)
class EntityIdentifier:
    """Идентификатор сущности. Immutable. Уже нормализован."""
    identifier_type: IdentifierType
    value: str
    entity_id: str = ""
    confidence: float = 1.0
    source_document_id: str = ""
