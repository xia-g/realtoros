"""
ProvenanceMetadata — metadata for KnowledgeProvenance.

Immutable. Infrastructure fields.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class ProvenanceMetadata:
    """Метаданные происхождения. Immutable."""
    created_at: datetime = field(default_factory=datetime.utcnow)
    source_count: int = 0
    confidence: float = 1.0
    revision_hint: int = 0