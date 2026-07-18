"""
KnowledgeRevision — immutable revision of knowledge.

Main model. NO diff/merge/apply/rollback/restore/compare methods.
"""
from __future__ import annotations

from dataclasses import dataclass

from domain.business_relationship.knowledge_revision_id import KnowledgeRevisionId
from domain.business_relationship.knowledge_revision_number import KnowledgeRevisionNumber
from domain.business_relationship.knowledge_snapshot import KnowledgeSnapshot
from domain.business_relationship.knowledge_revision_metadata import KnowledgeRevisionMetadata


@dataclass(frozen=True)
class KnowledgeRevision:
    """Ревизия знаний. Immutable. NO diff/merge/apply methods."""
    revision_id: KnowledgeRevisionId
    revision_number: KnowledgeRevisionNumber
    snapshot: KnowledgeSnapshot
    metadata: KnowledgeRevisionMetadata
