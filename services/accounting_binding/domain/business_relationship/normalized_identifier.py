"""
NormalizedIdentifier — result of normalization.

Immutable value object. Contains the canonical form of an identifier.
"""
from __future__ import annotations

from dataclasses import dataclass

from domain.business_relationship.entity_types import IdentifierType


@dataclass(frozen=True)
class NormalizedIdentifier:
    """Нормализованный идентификатор. Immutable."""
    identifier_type: IdentifierType
    original: str
    normalized: str
    confidence: float = 1.0

    @property
    def is_normalized(self) -> bool:
        return self.original != self.normalized
