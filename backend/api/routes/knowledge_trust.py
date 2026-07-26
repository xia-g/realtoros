"""Knowledge Trust State API — Capability поверх Platform v2.6.

Endpoints:
  GET /knowledge/trust/{revision_id}  — evaluate trust for a revision
  GET /knowledge/trust/latest         — evaluate trust for latest

No Platform changes.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from domain.business_relationship.knowledge_revision_id import KnowledgeRevisionId

from application.capabilities.trust_state import evaluate_trust

router = APIRouter(prefix="/knowledge", tags=["Knowledge Trust"])


def _get_integrator(request: Request):
    integrator = getattr(request.app.state, "integrator", None)
    if integrator is None:
        raise HTTPException(status_code=503, detail="Knowledge Runtime not available")
    return integrator


def _serialize(result) -> dict:
    return {
        "revision_id": result.revision_id,
        "trust": {
            "status": result.trust.status,
            "reasons": list(result.trust.reasons),
            "violations": [
                {"type": v.type, "severity": v.severity, "count": v.count}
                for v in result.trust.violations
            ],
            "structural_errors": result.trust.structural_errors,
            "structural_warnings": result.trust.structural_warnings,
            "node_count": result.trust.node_count,
            "edge_count": result.trust.edge_count,
            "provenance_coverage": result.trust.provenance_coverage,
        } if result.trust else None,
        "evaluated_at": result.evaluated_at,
        "has_provenance": result.has_provenance,
        "has_explanation": result.has_explanation,
    }


@router.get("/trust/latest")
async def get_latest_trust(request: Request):
    """Evaluate trust for the most recent revision."""
    from backend.config import settings
    import psycopg2
    import psycopg2.extras

    conn = psycopg2.connect(settings.DATABASE_SYNC_URL)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT revision_id FROM knowledge_revisions ORDER BY created_at DESC LIMIT 1")
            row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        return {"revision_id": "", "trust": None, "evaluated_at": ""}

    integrator = _get_integrator(request)
    repo = integrator.revision_repository
    record = repo.get(KnowledgeRevisionId(value=row["revision_id"]))
    if record is None:
        raise HTTPException(status_code=404, detail="Latest revision not found")

    result = evaluate_trust(
        snapshot=record.revision.snapshot,
        revision_id=row["revision_id"],
    )
    return _serialize(result)


@router.get("/trust/{revision_id}")
async def get_revision_trust(revision_id: str, request: Request):
    """Evaluate trust state for a KnowledgeRevision.

    Computes: VALID / WARNING / INVALID / UNKNOWN from snapshot structure.
    """
    integrator = _get_integrator(request)
    repo = integrator.revision_repository

    record = repo.get(KnowledgeRevisionId(value=revision_id))
    if record is None:
        raise HTTPException(status_code=404, detail=f"Revision not found: {revision_id}")

    result = evaluate_trust(
        snapshot=record.revision.snapshot,
        revision_id=revision_id,
    )

    return _serialize(result)
