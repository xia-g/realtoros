"""Knowledge Consistency Check API — Capability поверх Platform v2.4.

Endpoints:
  GET /knowledge/consistency/latest         — проверить последнюю revision
  GET /knowledge/consistency/{revision_id}  — проверить конкретную revision

No Platform changes.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from domain.business_relationship.knowledge_revision_id import KnowledgeRevisionId

from application.capabilities.consistency_check import check_snapshot_consistency

router = APIRouter(prefix="/knowledge", tags=["Knowledge Consistency"])


def _get_integrator(request: Request):
    integrator = getattr(request.app.state, "integrator", None)
    if integrator is None:
        raise HTTPException(status_code=503, detail="Knowledge Runtime not available")
    return integrator


def _serialize(result) -> dict:
    return {
        "revision_id": result.revision_id,
        "is_consistent": result.is_consistent,
        "violations": [
            {
                "severity": v.severity,
                "type": v.violation_type,
                "message": v.message,
                "affected_node_type": v.affected_node_type,
                "affected_domain_id": v.affected_domain_id,
                "affected_field": v.affected_field,
            }
            for v in result.violations
        ],
        "checked_nodes": result.checked_nodes,
        "checked_edges": result.checked_edges,
        "errors": result.errors,
        "warnings": result.warnings,
    }


# ── Latest first — FastAPI matches in declaration order ──


@router.get("/consistency/latest")
async def check_latest_consistency(request: Request):
    """Run structural consistency checks on the most recent revision."""
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
        return _serialize(check_snapshot_consistency.__wrapped__(None, revision_id=""))

    integrator = _get_integrator(request)
    repo = integrator.revision_repository
    record = repo.get(KnowledgeRevisionId(value=row["revision_id"]))
    if record is None:
        raise HTTPException(status_code=404, detail="Latest revision not found")

    snapshot = record.revision.snapshot
    result = check_snapshot_consistency(snapshot, revision_id=row["revision_id"])
    return _serialize(result)


@router.get("/consistency/{revision_id}")
async def check_revision_consistency(revision_id: str, request: Request):
    """Run structural consistency checks on a specific revision."""
    integrator = _get_integrator(request)
    repo = integrator.revision_repository

    record = repo.get(KnowledgeRevisionId(value=revision_id))
    if record is None:
        raise HTTPException(status_code=404, detail=f"Revision not found: {revision_id}")

    snapshot = record.revision.snapshot
    result = check_snapshot_consistency(snapshot, revision_id=revision_id)
    return _serialize(result)
