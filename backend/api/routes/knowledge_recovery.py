"""Knowledge Recovery API — Capability поверх Platform v2.8.

Endpoints:
  GET  /knowledge/recovery/plan/{revision_id}       — dry-run plan
  POST /knowledge/recovery/execute/{revision_id}    — execute (governance gated)

No Platform changes.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from domain.business_relationship.knowledge_revision_id import KnowledgeRevisionId

from application.capabilities.consistency_check import check_snapshot_consistency
from application.capabilities.trust_state import evaluate_trust
from application.capabilities.governance import evaluate_governance, GovernanceDecision
from application.capabilities.recovery import build_recovery_plan, execute_recovery

router = APIRouter(prefix="/knowledge", tags=["Knowledge Recovery"])


def _get_integrator(request: Request):
    integrator = getattr(request.app.state, "integrator", None)
    if integrator is None:
        raise HTTPException(status_code=503, detail="Knowledge Runtime not available")
    return integrator


def _get_record(revision_id: str, integrator):
    repo = integrator.revision_repository
    record = repo.get(KnowledgeRevisionId(value=revision_id))
    if record is None:
        raise HTTPException(status_code=404, detail=f"Revision not found: {revision_id}")
    return record, repo


@router.get("/recovery/plan/{revision_id}")
async def get_recovery_plan(revision_id: str, request: Request):
    """Dry-run recovery plan — shows what would be fixed, no changes."""
    integrator = _get_integrator(request)
    record, _ = _get_record(revision_id, integrator)

    snapshot = record.revision.snapshot
    consistency = check_snapshot_consistency(snapshot)

    # Check governance
    trust = evaluate_trust(snapshot, revision_id)
    if trust.trust:
        gov = evaluate_governance(trust.trust)
    else:
        gov = GovernanceDecision(
            decision="FLAGGED", reason="Cannot evaluate: no trust data",
            based_on_trust="UNKNOWN",
        )

    plan = build_recovery_plan(
        source_revision_id=revision_id,
        snapshot=snapshot,
        governance_decision=gov,
    )

    return {
        "source_revision_id": plan.source_revision_id,
        "governance_status": plan.governance_status,
        "governance_reason": gov.reason,
        "actions": [
            {
                "action_type": a.action_type,
                "violation_type": a.violation_type,
                "target_id": a.target_id,
                "description": a.description,
            }
            for a in plan.actions
        ],
        "violations_count": plan.violations_count,
        "actionable_count": plan.actionable_count,
    }


@router.post("/recovery/execute/{revision_id}")
async def execute_recovery_plan(revision_id: str, request: Request):
    """Execute a recovery plan — creates a new KnowledgeRevision.

    Requires Governance to be APPROVED.
    Original revision is never modified.
    """
    integrator = _get_integrator(request)
    record, repo = _get_record(revision_id, integrator)

    snapshot = record.revision.snapshot
    trust = evaluate_trust(snapshot, revision_id)
    if not trust.trust:
        raise HTTPException(status_code=400, detail="Cannot evaluate governance: no trust data")

    gov = evaluate_governance(trust.trust)

    if gov.decision != "APPROVED":
        raise HTTPException(
            status_code=400,
            detail=f"Recovery blocked: governance={gov.decision}, reason={gov.reason}",
        )

    result = execute_recovery(record, gov)

    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)

    # Save the new revision
    from application.knowledge_persistence.knowledge_revision_record import KnowledgeRevisionRecord

    # Rebuild the record from the result
    from domain.business_relationship.knowledge_revision import KnowledgeRevision as KR
    from domain.business_relationship.knowledge_revision_id import KnowledgeRevisionId as KRID
    from domain.business_relationship.knowledge_revision_number import KnowledgeRevisionNumber as KRN
    from domain.business_relationship.knowledge_revision_metadata import KnowledgeRevisionMetadata as KRM
    from datetime import datetime, timezone

    source_rev = record.revision
    repaired_snapshot, actions = None, ()

    # Re-execute to get the snapshot — since execute_recovery doesn't return it
    from application.capabilities.recovery import _repair_snapshot
    repaired_snapshot, _ = _repair_snapshot(snapshot, check_snapshot_consistency(snapshot).violations)

    new_rev = KR(
        revision_id=KRID(value=result.recovery_revision_id),
        revision_number=KRN(number=source_rev.revision_number.number + 1),
        snapshot=repaired_snapshot,
        metadata=KRM(
            created_at=datetime.now(timezone.utc),
            created_by="system:recovery",
            reason=f"Recovery from {source_rev.revision_id.value}: {result.message}",
            document_count=1,
        ),
    )

    new_record = KnowledgeRevisionRecord(
        revision=new_rev,
        explanation=new_rev.snapshot.explanation,
        source_document_id=record.source_document_id,
    )

    repo.save(new_record)

    return {
        "source_revision_id": result.source_revision_id,
        "recovery_revision_id": new_rev.revision_id.value,
        "actions_performed": result.actions_performed,
        "success": True,
        "message": result.message,
    }
