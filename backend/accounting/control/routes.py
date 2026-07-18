"""Control Plane API routes for Phase 7."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.accounting.db.pool import get_pool
from backend.accounting.control import ControlPlaneOrchestrator

router = APIRouter(prefix="/control", tags=["Control"])


# ── System State ───────────────────────────────────────────────────────


@router.get("/state")
async def get_system_state(
    subsystem: str | None = None,
):
    """Get current system health state for all or one subsystem."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        if subsystem:
            rows = await conn.fetch(
                "SELECT * FROM accounting.system_state WHERE subsystem = $1",
                subsystem,
            )
        else:
            rows = await conn.fetch("SELECT * FROM accounting.system_state ORDER BY subsystem")
        return {"items": [dict(r) for r in rows]}


# ── Actions ────────────────────────────────────────────────────────────


@router.get("/actions")
async def list_actions(
    action_type: str | None = None,
    target_system: str | None = None,
    status: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List control actions (immutable audit log)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        where = ["1=1"]
        params = []
        idx = 1
        if action_type:
            where.append(f"action_type = ${idx}")
            params.append(action_type)
            idx += 1
        if target_system:
            where.append(f"target_system = ${idx}")
            params.append(target_system)
            idx += 1
        if status:
            where.append(f"status = ${idx}")
            params.append(status)
            idx += 1

        w = " AND ".join(where)
        total = await conn.fetchval(
            f"SELECT count(*) FROM accounting.control_action WHERE {w}",
            *params,
        )
        rows = await conn.fetch(
            f"""SELECT * FROM accounting.control_action
                WHERE {w}
                ORDER BY created_at DESC
                LIMIT ${idx} OFFSET ${idx+1}""",
            *params, limit, offset,
        )
        return {"total": total, "items": [dict(r) for r in rows]}


@router.get("/actions/{action_id}")
async def get_action(action_id: str):
    """Get a single control action with audit trail."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        action = await conn.fetchrow(
            "SELECT * FROM accounting.control_action WHERE id = $1",
            action_id,
        )
        if not action:
            raise HTTPException(status_code=404, detail="Action not found")

        approvals = await conn.fetch(
            "SELECT * FROM accounting.approval_workflow WHERE action_id = $1",
            action_id,
        )
        return {"action": dict(action), "approvals": [dict(a) for a in approvals]}


@router.post("/actions/execute")
async def execute_action(body: dict):
    """Execute a control action with permission check + audit."""
    action_type = body.get("action_type")
    target_system = body.get("target_system")
    actor_id = body.get("actor_id")
    actor_role = body.get("actor_role", "system_operator")
    details = body.get("details", {})

    if not action_type or not target_system:
        raise HTTPException(status_code=400, detail="action_type and target_system required")

    result = await ControlPlaneOrchestrator.execute_action(
        action_type=action_type,
        target_system=target_system,
        actor_id=actor_id,
        actor_role=actor_role,
        details=details,
        correlation_id=body.get("correlation_id"),
    )

    if "error" in result:
        raise HTTPException(status_code=403, detail=result["error"])

    return result


@router.post("/actions/{action_id}/approve")
async def approve_action(action_id: str, body: dict):
    """Approve a pending action (human approval)."""
    approved_by = body.get("approved_by")
    role = body.get("role", "admin")
    reason = body.get("reason")

    if not approved_by:
        raise HTTPException(status_code=400, detail="approved_by required")

    result = await ControlPlaneOrchestrator.approve_action(
        action_id=action_id,
        approved_by=approved_by,
        role=role,
        reason=reason,
    )

    if "error" in result:
        raise HTTPException(status_code=403, detail=result["error"])

    return result


# ── Metrics ────────────────────────────────────────────────────────────


@router.post("/metrics")
async def record_metrics():
    """Record a system metrics snapshot."""
    result = await ControlPlaneOrchestrator.record_metrics()
    return result


@router.get("/metrics")
async def get_metrics(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Get system metrics snapshots."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval("SELECT count(*) FROM accounting.system_metrics_snapshot")
        rows = await conn.fetch(
            """SELECT * FROM accounting.system_metrics_snapshot
               ORDER BY snapshot_time DESC
               LIMIT $1 OFFSET $2""",
            limit, offset,
        )
        return {"total": total, "items": [dict(r) for r in rows]}
