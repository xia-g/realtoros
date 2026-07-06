"""
KnowledgeRevision — immutable, monotonic snapshot of corporate knowledge.

Each successful document processing produces a new revision.
Revisions are append-only. NO mutation.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from domain.business_relationship.knowledge_state import KnowledgeState


@dataclass(frozen=True)
class KnowledgeRevision:
    """Immutable snapshot of knowledge at a point in time."""
    revision_number: int
    state: KnowledgeState
    revision_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    previous_revision: int | None = None
    created_from_documents: list[str] = field(default_factory=list)
    summary: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "revision": self.revision_number,
            "previous": self.previous_revision,
            "summary": self.summary,
            "documents": self.created_from_documents,
            "state": self.state.to_dict(),
            "created_at": self.created_at.isoformat(),
        }
