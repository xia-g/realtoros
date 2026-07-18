"""
KnowledgeRevisionRecord — immutable application-level DTO.

Binds KnowledgeRevision with GraphExplanation and source document reference.
NOT part of Domain. NOT part of Projection Layer.
Persistence envelope only.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from domain.business_relationship.knowledge_revision import KnowledgeRevision
from domain.business_relationship.ke_explanation import GraphExplanation


@dataclass(frozen=True)
class KnowledgeRevisionRecord:
    """Persistence envelope for a complete document processing result.

    Immutable. Value-based equality via frozen dataclass.

    Note: KnowledgeSnapshot already includes provenance and explanation,
    so revision.snapshot.provenance and revision.snapshot.explanation
    are available directly.

    Fields:
        revision: KnowledgeRevision — Domain System of Record
        explanation: GraphExplanation — per-document explainability
        source_document_id: str — originating document identifier
        processing_job_id: str | None — OCR job / upload job id
        created_at: datetime — when this record was created
    """
    revision: KnowledgeRevision
    explanation: GraphExplanation
    source_document_id: str
    processing_job_id: str | None = None
    created_at: datetime = datetime.min
