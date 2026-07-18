"""
RevisionReference — immutable reference between revisions.

Parent/derived links. NO navigation. NO traversal.
"""
from __future__ import annotations

from dataclasses import dataclass

from domain.business_relationship.knowledge_revision_id import KnowledgeRevisionId


@dataclass(frozen=True)
class RevisionReference:
    """Ссылка на предыдущую или производную ревизию. Immutable."""
    parent_revision_id: KnowledgeRevisionId
    derived_revision_id: KnowledgeRevisionId
    reason: str = ""
