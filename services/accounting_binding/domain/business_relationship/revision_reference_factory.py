"""
RevisionReferenceFactory — creates RevisionReference from revision IDs.

Stateless. NO builder knowledge. Only pure transformation.
"""
from __future__ import annotations

from domain.business_relationship.knowledge_revision_id import KnowledgeRevisionId
from domain.business_relationship.revision_reference import RevisionReference


class RevisionReferenceFactory:
    """Создаёт RevisionReference. Не знает Builder."""

    @staticmethod
    def parent(parent_id: KnowledgeRevisionId, derived_id: KnowledgeRevisionId) -> RevisionReference:
        """Create parent-derived reference."""
        return RevisionReference(
            parent_revision_id=parent_id,
            derived_revision_id=derived_id,
        )

    @staticmethod
    def derived(derived_id: KnowledgeRevisionId, parent_id: KnowledgeRevisionId) -> RevisionReference:
        """Create derived reference (alias for parent)."""
        return RevisionReference(
            parent_revision_id=parent_id,
            derived_revision_id=derived_id,
        )

    @staticmethod
    def branched(
        branch_id: KnowledgeRevisionId,
        source_id: KnowledgeRevisionId,
    ) -> RevisionReference:
        """Create branch reference from source."""
        return RevisionReference(
            parent_revision_id=source_id,
            derived_revision_id=branch_id,
        )
