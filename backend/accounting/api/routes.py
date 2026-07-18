"""Accounting API endpoints for Phase 2."""

from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from backend.accounting.db.pool import get_pool
from backend.accounting.replay.service import recalculate
from backend.accounting.metrics.collector import metrics
from backend.accounting.orchestrator.dead_letter import get_dlq_events, reprocess_manually

router = APIRouter(prefix="/accounting", tags=["Accounting"])


# ── Events ──────────────────────────────────────────────────────────────


@router.get("/events")
async def list_events(
    company_id: str | None = None,
    decision_state: str | None = None,
    processing_state: str | None = None,
    is_current: bool = True,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List accounting events with filters."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        where = ["is_current = $1"]
        params = [is_current]
        idx = 2

        if company_id:
            where.append(f"company_id = ${idx}")
            params.append(company_id)
            idx += 1
        if decision_state:
            where.append(f"decision_state = ${idx}")
            params.append(decision_state)
            idx += 1
        if processing_state:
            where.append(f"processing_state = ${idx}")
            params.append(processing_state)
            idx += 1

        where_clause = " AND ".join(where)
        count = await conn.fetchval(
            f"SELECT count(*) FROM accounting.accounting_event WHERE {where_clause}",
            *params,
        )
        rows = await conn.fetch(
            f"""SELECT id, company_id, event_type, event_date, amount, currency,
                      source_system, source_type, source_id, recognition_status,
                      decision_state, processing_state, current_decision_id,
                      is_current, version, superseded_reason, attempt_count,
                      last_error, created_at, updated_at
               FROM accounting.accounting_event
               WHERE {where_clause}
               ORDER BY event_date DESC
               LIMIT ${idx} OFFSET ${idx + 1}""",
            *params,
            limit,
            offset,
        )
        return {
            "total": count,
            "limit": limit,
            "offset": offset,
            "items": [dict(r) for r in rows],
        }


@router.get("/events/{event_id}")
async def get_event(event_id: str):
    """Get a single event with all details."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM accounting.accounting_event WHERE id = $1",
            event_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="Event not found")
        return dict(row)


# ── Decision & Explanations ─────────────────────────────────────────────


@router.get("/events/{event_id}/decision")
async def get_decision(event_id: str):
    """Get the current active decision for an event."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM accounting.accounting_decision WHERE event_id = $1 AND superseded_at IS NULL",
            event_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="No active decision found")
        return dict(row)


@router.get("/events/{event_id}/explanations")
async def get_explanations(event_id: str):
    """Get all explanations for the current decision."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        decision = await conn.fetchrow(
            "SELECT id FROM accounting.accounting_decision WHERE event_id = $1 AND superseded_at IS NULL",
            event_id,
        )
        if not decision:
            raise HTTPException(status_code=404, detail="No active decision found")

        rows = await conn.fetch(
            "SELECT * FROM accounting.decision_explanation WHERE decision_id = $1 ORDER BY weight DESC",
            decision["id"],
        )
        return {"decision_id": decision["id"], "explanations": [dict(r) for r in rows]}


# ── Batches ──────────────────────────────────────────────────────────────


@router.get("/batches/{batch_id}")
async def get_batch(batch_id: str):
    """Get a batch with its events."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        batch = await conn.fetchrow(
            "SELECT * FROM accounting.accounting_batch WHERE id = $1",
            batch_id,
        )
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")

        events = await conn.fetch(
            "SELECT id, event_type, event_date, amount, currency, decision_state, processing_state "
            "FROM accounting.accounting_event WHERE batch_id = $1 ORDER BY event_date",
            batch_id,
        )
        return {"batch": dict(batch), "events": [dict(e) for e in events]}


# ── Replay ───────────────────────────────────────────────────────────────


@router.post("/replay")
async def replay_event(body: dict):
    """Recalculate a decision for an event.

    Body:
    {
        "event_id": "uuid",
        "snapshot_version": 1,           # optional, latest if omitted
        "ruleset_version": "2026.06.15"  # optional, today if omitted
    }
    """
    event_id = body.get("event_id")
    if not event_id:
        raise HTTPException(status_code=400, detail="event_id is required")

    try:
        result = await recalculate(
            event_id=event_id,
            snapshot_version=body.get("snapshot_version"),
            ruleset_version=body.get("ruleset_version"),
        )
        return {
            "new_decision_id": result.new_decision_id,
            "old_decision_id": result.old_decision_id,
            "old_included": result.old_included,
            "new_included": result.new_included,
            "old_ruleset_version": result.old_ruleset_version,
            "new_ruleset_version": result.new_ruleset_version,
            "diff": result.diff,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── DLQ ──────────────────────────────────────────────────────────────────


@router.get("/dlq")
async def list_dlq(limit: int = Query(50, ge=1, le=500)):
    """List events in the dead letter queue."""
    events = await get_dlq_events(limit)
    return {"total": len(events), "items": events}


@router.post("/dlq/{event_id}/reprocess")
async def reprocess_dlq(event_id: str):
    """Move a DLQ'd event back to NEW for manual reprocessing."""
    success = await reprocess_manually(event_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to reprocess event")
    return {"status": "ok", "event_id": event_id, "new_state": "new"}


# ── Metrics ──────────────────────────────────────────────────────────────


@router.get("/metrics")
async def get_metrics():
    """Get pipeline metrics."""
    return metrics.snapshot()


@router.post("/metrics/reset")
async def reset_metrics():
    """Reset all metrics counters."""
    metrics.reset()
    return {"status": "ok"}
