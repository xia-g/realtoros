"""
MemoryKnowledgeRevisionRepository — in-memory implementation of KnowledgeRevisionRepository.

Reference implementation. Thread-safe for single-threaded access.
"""
from __future__ import annotations

from typing import Optional

from domain.business_relationship.knowledge_revision_id import KnowledgeRevisionId
from application.knowledge_persistence.knowledge_revision_record import KnowledgeRevisionRecord
from application.knowledge_persistence.knowledge_revision_repository import (
    KnowledgeRevisionRepository,
    KnowledgeRevisionConflictError,
)


class MemoryKnowledgeRevisionRepository:
    """In-memory implementation of KnowledgeRevisionRepository.

    Semantics:
    - save() with same revision_id and identical record → idempotent success
    - save() with same revision_id but different content → KnowledgeRevisionConflictError
    - get() returns None for missing revision
    - get_by_document_id() returns all revisions for a document
    """

    def __init__(self) -> None:
        self._store: dict[str, KnowledgeRevisionRecord] = {}
        self._by_doc_id: dict[str, set[str]] = {}

    def save(self, record: KnowledgeRevisionRecord) -> None:
        rev_id = str(record.revision.revision_id.value)
        existing = self._store.get(rev_id)
        if existing is not None:
            if existing == record:
                return  # idempotent: same content
            raise KnowledgeRevisionConflictError(
                f"Revision {rev_id} already exists with different content"
            )
        self._store[rev_id] = record
        doc_id = record.source_document_id
        if doc_id not in self._by_doc_id:
            self._by_doc_id[doc_id] = set()
        self._by_doc_id[doc_id].add(rev_id)

    def get(self, revision_id: KnowledgeRevisionId) -> KnowledgeRevisionRecord | None:
        return self._store.get(str(revision_id.value))

    def get_by_document_id(
        self,
        source_document_id: str,
    ) -> tuple[KnowledgeRevisionRecord, ...]:
        rev_ids = self._by_doc_id.get(source_document_id, set())
        return tuple(self._store[rid] for rid in rev_ids if rid in self._store)

    def __len__(self) -> int:
        return len(self._store)
