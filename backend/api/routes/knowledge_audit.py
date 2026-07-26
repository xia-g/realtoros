"""Knowledge Audit Trail API — Capability поверх Platform v2.5.

Endpoints:
  GET /knowledge/audit/{revision_id}  — audit trail for a revision

No Platform changes.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from domain.business_relationship.knowledge_revision_id import KnowledgeRevisionId
from application.capabilities.audit_service import KnowledgeAuditService

router = APIRouter(prefix="/knowledge", tags=["Knowledge Audit"])


def _get_integrator(request: Request):
    integrator = getattr(request.app.state, "integrator", None)
    if integrator is None:
        raise HTTPException(status_code=503, detail="Knowledge Runtime not available")
    return integrator


def _serialize(result) -> dict:
    def _rev_summary(r) -> dict | None:
        if r is None:
            return None
        return {
            "revision_id": r.revision_id,
            "revision_number": r.revision_number,
            "created_at": r.created_at,
            "created_by": r.created_by,
            "reason": r.reason,
            "source_document_id": r.source_document_id,
        }

    return {
        "revision": _rev_summary(result.revision),
        "provenance": [
            {
                "source_type": p.source_type,
                "source_id": p.source_id,
                "description": p.description,
                "confidence": p.confidence,
            }
            for p in result.provenance
        ],
        "validation": {
            "is_consistent": result.validation.is_consistent,
            "violations_count": result.validation.violations_count,
            "errors": result.validation.errors,
            "warnings": result.validation.warnings,
        } if result.validation else None,
        "previous_revision": _rev_summary(result.previous_revision),
        "next_revision": _rev_summary(result.next_revision),
        "total_revisions_for_document": result.total_revisions_for_document,
    }


@router.get("/audit/{revision_id}")
async def get_revision_audit(revision_id: str, request: Request):
    """Full audit trail for a KnowledgeRevision.

    Returns:
      - revision metadata
      - provenance from KnowledgeSnapshot
      - Consistency Check result (computed on demand)
      - previous / next revision in document timeline
    """
    integrator = _get_integrator(request)
    repo = integrator.revision_repository

    from backend.config import settings

    record = repo.get(KnowledgeRevisionId(value=revision_id))
    if record is None:
        raise HTTPException(status_code=404, detail=f"Revision not found: {revision_id}")

    service = KnowledgeAuditService(dsn=settings.DATABASE_SYNC_URL)
    result = service.build_audit(
        revision=record.revision,
        source_document_id=record.source_document_id,
    )

    return _serialize(result)
