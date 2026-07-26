"""Knowledge Governance API — Capability поверх Platform v2.7.

Endpoints:
  GET /knowledge/governance/check/latest        — latest revision
  GET /knowledge/governance/check/{revision_id} — specific revision

No Platform changes.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from domain.business_relationship.knowledge_revision_id import KnowledgeRevisionId

from application.capabilities.trust_state import evaluate_trust
from application.capabilities.governance import build_governance

router = APIRouter(prefix="/knowledge", tags=["Knowledge Governance"])


def _get_integrator(request: Request):
    integrator = getattr(request.app.state, "integrator", None)
    if integrator is None:
        raise HTTPException(status_code=503, detail="Knowledge Runtime not available")
    return integrator


def _serialize(result) -> dict:
    return {
        "revision_id": result.revision_id,
        "decision": {
            "status": result.decision.decision,
            "reason": result.decision.reason,
            "based_on_trust": result.decision.based_on_trust,
            "structural_errors": result.decision.structural_errors,
            "structural_warnings": result.decision.structural_warnings,
            "provenance_coverage": result.decision.provenance_coverage,
        },
        "evaluated_at": result.evaluated_at,
    }


@router.get("/governance/check/latest")
async def check_latest_governance(request: Request):
    """Evaluate governance for the most recent revision."""
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
        return {"revision_id": "", "decision": None, "evaluated_at": ""}

    integrator = _get_integrator(request)
    repo = integrator.revision_repository
    record = repo.get(KnowledgeRevisionId(value=row["revision_id"]))
    if record is None:
        raise HTTPException(status_code=404, detail="Latest revision not found")

    trust = evaluate_trust(snapshot=record.revision.snapshot, revision_id=row["revision_id"])
    result = build_governance(revision_id=row["revision_id"], trust_evaluation=trust)
    return _serialize(result)


@router.get("/governance/check/{revision_id}")
async def check_governance(revision_id: str, request: Request):
    """Evaluate governance decision for a KnowledgeRevision.

    Combines Trust State evaluation + Governance rules.
    Returns APPROVED / FLAGGED / REJECTED.
    """
    integrator = _get_integrator(request)
    repo = integrator.revision_repository

    record = repo.get(KnowledgeRevisionId(value=revision_id))
    if record is None:
        raise HTTPException(status_code=404, detail=f"Revision not found: {revision_id}")

    trust = evaluate_trust(snapshot=record.revision.snapshot, revision_id=revision_id)
    result = build_governance(revision_id=revision_id, trust_evaluation=trust)
    return _serialize(result)
