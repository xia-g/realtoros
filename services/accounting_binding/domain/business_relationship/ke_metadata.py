"""
KnowledgeMetadata — non-business metadata for knowledge models.

Immutable. Infrastructure-relevant fields only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class KnowledgeMetadata:
    """Метаданные знания. Не бизнес-логика."""
    created_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = ""
    revision_hint: int = 0
    source_count: int = 0
