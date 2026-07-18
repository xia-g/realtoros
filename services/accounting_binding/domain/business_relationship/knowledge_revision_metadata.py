"""
KnowledgeRevisionMetadata — metadata for KnowledgeRevision.

Immutable. Infrastructure fields.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class KnowledgeRevisionMetadata:
    """Метаданные ревизии. Immutable."""
    created_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str = ""
    reason: str = ""
    document_count: int = 0
    entity_count: int = 0
    graph_digest_hint: str = ""
