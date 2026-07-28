"""TEMPORARY: Document projection layer (Epic 3 remediation).

For now, we read directly from document_intake. The long-term architecture
should implement a proper Document Projection (document_intake → documents).
See: docs/epic3-remediation-plan.md

This module provides a compatibility layer that maps document_intake columns
to the Document model for backward compatibility with existing code that expects Document objects.
"""

from __future__ import annotations

from uuid import UUID
from datetime import datetime

from sqlalchemy import text
from structlog import get_logger

from backend.models.document import Document

logger = get_logger(__name__)


async def _load_document_from_intake(session, document_id: UUID) -> Document | None:
    """
    Load document from document_intake (temporary compatibility layer).
    
    Maps document_intake columns to Document model fields for backward
    compatibility with existing code that expects Document objects.
    
    TODO: Replace with proper Document Projection layer that reads from
    document_intake and writes to documents. This should be a separate
    module that implements the projection logic.
    """
    row = await session.execute(
        text("""
            SELECT 
                id AS document_id,
                file_name,
                file_size,
                mime_type,
                classification AS document_type,
                extracted_text AS description,
                confidence,
                extracted_fields,
                'processed' AS status,
                NOW() AS created_at
            FROM accounting.document_intake
            WHERE id = :doc_id
        """),
        {"doc_id": str(document_id)}
    )
    row = row.fetchone()
    
    if not row:
        logger.warning(
            "knowledge_runtime_document_not_found",
            document_id=str(document_id),
            message="Document not found in document_intake"
        )
        return None
    
    # Map document_intake fields to Document fields
    # Note: This is a temporary mapping; proper projection layer should handle
    # all field mappings and business logic
    return Document(
        id=row["document_id"],
        document_type=row.get("document_type", "unknown"),
        status=row.get("status", "processed"),
        title=row["file_name"],  # Use filename as title
        description=row.get("description"),
        file_name=row["file_name"],
        file_path=f"/tmp/{row['file_name']}",  # Temporary path
        file_size=row.get("file_size"),
        file_hash="",  # Not available in document_intake
        mime_type=row.get("mime_type"),
        created_at=row.get("created_at", datetime.utcnow()),
        deleted_at=None,
    )
