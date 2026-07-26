"""Stream 3 — Document Intelligence & Routing API.

Endpoints:
  POST /documents/{id}/route                  — Evaluate + route
  GET  /documents/{id}/route                  — Current routing decision
  GET  /routing/decisions/{decision_id}       — Full decision
  POST /routing/decisions/{decision_id}/override — Manual override

Product Layer, not Platform.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from backend.services.routing.models import (
    RoutingEngine, RoutingDecision, RoutingResult,
)
from backend.services.routing.storage import RoutingRepository
from backend.services.routing.matcher import EntityMatcher
from backend.services.document_lifecycle import DocumentRepository, transition_document

router = APIRouter(prefix="/routing", tags=["Document Routing"])


def _get_repo(request: Request) -> RoutingRepository:
    from backend.config import settings
    return RoutingRepository(settings.DATABASE_SYNC_URL)


def _get_doc_repo(request: Request):
    from backend.config import settings
    return DocumentRepository(settings.DATABASE_SYNC_URL)


def _get_engine() -> RoutingEngine:
    return RoutingEngine()


def _get_matcher(request: Request) -> EntityMatcher:
    from backend.config import settings
    return EntityMatcher(settings.DATABASE_SYNC_URL)


def _serialize_decision(d: RoutingDecision) -> dict:
    return {
        "decision_id": d.decision_id,
        "document_id": d.document_id,
        "rule_id": d.rule_id,
        "destination": d.destination,
        "status": d.status,
        "confidence": d.confidence,
        "matched_entities": d.matched_entities,
        "needs_approval": d.needs_approval,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "routed_at": d.routed_at.isoformat() if d.routed_at else None,
        "is_final": d.is_final,
    }


@router.post("/documents/{document_id}/route")
async def evaluate_routing(document_id: str, request: Request):
    """Evaluate routing for an analyzed document.

    Document must be in ANALYZED status.
    Returns RoutingDecision.
    """
    doc_repo = _get_doc_repo(request)
    doc = doc_repo.get(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")

    if doc.status not in ("ANALYZED", "DECIDED", "NEEDS_REVIEW", "FAILED"):
        raise HTTPException(
            status_code=400,
            detail=f"Document must be ANALYZED to route (current: {doc.status})",
        )

    # Check if already routed
    repo = _get_repo(request)
    existing = repo.get_decision_by_document(document_id)
    if existing and existing.is_final:
        return _serialize_decision(existing)

    # Evaluate routing rules
    engine = _get_engine()
    profile = doc.profile or {}
    # Ensure document_type is in profile
    if "document_type" not in profile and "type" in profile:
        profile["document_type"] = profile["type"]

    result: RoutingResult = engine.evaluate(profile)

    # Entity matching
    try:
        matcher = _get_matcher(request)
        fields = profile.get("fields", {})
        doc_type = profile.get("document_type", "unknown")
        matched_entities = matcher.resolve(fields, doc_type)
    except Exception:
        matched_entities = {}

    # Create decision
    decision = RoutingDecision(
        decision_id=str(uuid.uuid4()),
        document_id=document_id,
        rule_id=result.rule_id,
        destination=result.destination,
        confidence=result.confidence,
        matched_entities=matched_entities,
        needs_approval=result.needs_approval,
        created_at=datetime.now(timezone.utc),
        status="DECIDED",
    )

    # Auto-route if no approval needed
    if not result.needs_approval and result.matched:
        decision.status = "ROUTED"
        decision.routed_at = datetime.now(timezone.utc)
        decision.metadata = {"event": "DocumentRouted", "source": "routing_engine"}

    repo.save_decision(decision)

    # Update document status
    if decision.status == "ROUTED":
        doc.status = "ROUTED"
        doc.pipeline_stage = f"routed_to_{result.destination}"
    else:
        err = transition_document(doc, "DECIDED")
        if not err:
            doc.status = "DECIDED"
        doc.pipeline_stage = f"decided_{result.destination}"
    doc_repo.save(doc)

    return _serialize_decision(decision)


@router.get("/documents/{document_id}/route")
async def get_document_routing(document_id: str, request: Request):
    """Get current routing decision for a document."""
    repo = _get_repo(request)
    decision = repo.get_decision_by_document(document_id)
    if decision is None:
        return {"decision_id": None, "document_id": document_id, "status": "NOT_ROUTED"}
    return _serialize_decision(decision)


@router.get("/decisions/{decision_id}")
async def get_routing_decision(decision_id: str, request: Request):
    """Get full routing decision details."""
    repo = _get_repo(request)
    decision = repo.get_decision(decision_id)
    if decision is None:
        raise HTTPException(status_code=404, detail=f"Decision not found: {decision_id}")
    return _serialize_decision(decision)


@router.post("/decisions/{decision_id}/override")
async def override_routing_decision(decision_id: str, request: Request):
    """Manually override a routing decision.

    Body: {"destination": "new_destination"}
    """
    body = await request.json()
    new_destination = body.get("destination", "")
    if not new_destination:
        raise HTTPException(status_code=400, detail="destination is required")

    repo = _get_repo(request)
    decision = repo.get_decision(decision_id)
    if decision is None:
        raise HTTPException(status_code=404, detail=f"Decision not found: {decision_id}")

    old_destination = decision.destination
    decision.destination = new_destination
    decision.status = "OVERRIDDEN"
    decision.routed_at = datetime.now(timezone.utc)
    decision.metadata.update({
        "event": "RoutingOverridden",
        "previous_destination": old_destination,
        "new_destination": new_destination,
        "overridden_at": decision.routed_at.isoformat(),
    })
    repo.save_decision(decision)

    # Update document
    doc_repo = _get_doc_repo(request)
    doc = doc_repo.get(decision.document_id)
    if doc:
        doc.status = "ROUTED"
        doc.pipeline_stage = f"routed_to_{new_destination}"
        doc_repo.save(doc)

    return _serialize_decision(decision)
