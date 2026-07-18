"""
IdentityMetadata — non-business metadata for CanonicalEntity.

Immutable value object. Infrastructure-relevant fields only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class IdentityMetadata:
    """Метаданные канонической сущности. Не бизнес-логика."""
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    confidence: float = 1.0
