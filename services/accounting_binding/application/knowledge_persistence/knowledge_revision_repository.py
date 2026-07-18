"""
KnowledgeRevisionRepository — persistence protocol for KnowledgeRevisionRecord.

Only save + get + get_by_document_id.
No business logic. No Domain knowledge. No Projection.
"""
from __future__ import annotations

from typing import Protocol as TypedProtocol

from domain.business_relationship.knowledge_revision_id import KnowledgeRevisionId
from application.knowledge_persistence.knowledge_revision_record import KnowledgeRevisionRecord


class KnowledgeRevisionRepository(TypedProtocol):
    """Repository for persisting document processing results.

    Only responsible for:
    - saving a KnowledgeRevisionRecord
    - retrieving by revision id
    - retrieving all revisions for a document

    NOT responsible for:
    - building revisions
    - building projections
    - executing queries
    - merging conflicts
    """

    def save(self, record: KnowledgeRevisionRecord) -> None:
        """Persist a revision record.

        Raises:
            KnowledgeRevisionConflictError: if same revision_id with different content
        """
        ...

    def get(self, revision_id: KnowledgeRevisionId) -> KnowledgeRevisionRecord | None:
        """Retrieve a revision record by its id. Returns None if not found."""
        ...

    def get_by_document_id(
        self,
        source_document_id: str,
    ) -> tuple[KnowledgeRevisionRecord, ...]:
        """Retrieve all revision records for a given source document."""
        ...


class KnowledgeRevisionConflictError(ValueError):
    """Raised when attempting to save a revision with same id but different content."""
    pass
