"""Reconciliation API routes for Phase 6."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query

from backend.accounting.db.pool import get_pool
from backend.accounting.reconciliation.engine import ReconciliationEngine, ExternalSystemConnector

router = APIRouter(prefix="/reconciliation", tags=["Reconciliation"])


@router.post("/run")
async def create_run(body: dict):
    """Execute a reconciliation run for a period.

    Steps:
      1. Fetch ledger + bank data (read-only)
      2. Match items deterministically
      3. Detect gaps
      4. Persist run (immutable)

    Returns run_id + summary.
    """
    company_id = body.get("company_id")
    period_from_str = body.get("period_from")
    period_to_str = body.get("period_to")

    if not company_id or not period_from_str or not period_to_str:
        raise HTTPException(status_code=400, detail="company_id, period_from, period_to required")

    try:
        period_from = date.fromisoformat(period_from_str)
        period_to = date.fromisoformat(period_to_str)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="period_from and period_to must be ISO dates (YYYY-MM-DD)")

    result = await ReconciliationEngine.run(company_id, period_from, period_to)
    run_id = await ReconciliationEngine.save(result)

    return {
        "run_id": run_id,
        "run_hash": result.run_hash,
        "status": result.status,
        "summary": {
            "ledger_entries": result.ledger_count,
            "bank_entries": result.bank_count,
            "matches_count": result.matches_count,
            "gaps_count": result.gaps_count,
        },
        "defails": {
            "ledger": result.ledger_count,
            "bank": result.bank_count,
        },
    }


@router.get("/runs")
async def list_runs(
    company_id: str | None = None,
    status: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List reconciliation runs."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        where = ["1=1"]
        params = []
        idx = 1
        if company_id:
            where.append(f"company_id = ${idx}")
            params.append(company_id)
            idx += 1
        if status:
            where.append(f"status = ${idx}")
            params.append(status)
            idx += 1

        w = " AND ".join(where)
        total = await conn.fetchval(
            f"SELECT count(*) FROM accounting.reconciliation_run WHERE {w}",
            *params,
        )
        rows = await conn.fetch(
            f"""SELECT id, run_version, status, source_systems,
                      period_from, period_to,
                      ledger_entries_count, bank_entries_count,
                      matches_count, gaps_count, run_hash,
                      created_at, closed_at
               FROM accounting.reconciliation_run
               WHERE {w}
               ORDER BY created_at DESC
               LIMIT ${idx} OFFSET ${idx+1}""",
            *params, limit, offset,
        )
        return {"total": total, "items": [dict(r) for r in rows]}


@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    """Get a reconciliation run with summary."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        run = await conn.fetchrow(
            "SELECT * FROM accounting.reconciliation_run WHERE id = $1",
            run_id,
        )
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")

        return {"run": dict(run)}


@router.get("/runs/{run_id}/matches")
async def get_matches(
    run_id: str,
    match_type: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Get matching results for a reconciliation run."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        where = ["run_id = $1"]
        params = [run_id]
        idx = 2
        if match_type:
            where.append(f"match_type = ${idx}")
            params.append(match_type)
            idx += 1

        w = " AND ".join(where)
        total = await conn.fetchval(
            f"SELECT count(*) FROM accounting.reconciliation_match WHERE {w}",
            *params,
        )
        rows = await conn.fetch(
            f"""SELECT * FROM accounting.reconciliation_match
                WHERE {w}
                ORDER BY confidence_score DESC
                LIMIT ${idx} OFFSET ${idx+1}""",
            *params, limit, offset,
        )
        return {"total": total, "items": [dict(r) for r in rows]}


@router.get("/runs/{run_id}/gaps")
async def get_gaps(
    run_id: str,
    severity: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Get gaps detected in a reconciliation run."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        where = ["run_id = $1"]
        params = [run_id]
        idx = 2
        if severity:
            where.append(f"severity = ${idx}")
            params.append(severity)
            idx += 1

        w = " AND ".join(where)
        total = await conn.fetchval(
            f"SELECT count(*) FROM accounting.reconciliation_gap WHERE {w}",
            *params,
        )
        rows = await conn.fetch(
            f"""SELECT * FROM accounting.reconciliation_gap
                WHERE {w}
                ORDER BY
                  CASE severity WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END,
                  amount DESC
                LIMIT ${idx} OFFSET ${idx+1}""",
            *params, limit, offset,
        )
        return {"total": total, "items": [dict(r) for r in rows]}


@router.get("/runs/{run_id}/items")
async def get_items(
    run_id: str,
    system: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Get items compared in a reconciliation run."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        where = ["run_id = $1"]
        params = [run_id]
        idx = 2
        if system:
            where.append(f"system = ${idx}")
            params.append(system)
            idx += 1

        w = " AND ".join(where)
        total = await conn.fetchval(
            f"SELECT count(*) FROM accounting.reconciliation_item WHERE {w}",
            *params,
        )
        rows = await conn.fetch(
            f"""SELECT * FROM accounting.reconciliation_item
                WHERE {w}
                ORDER BY item_date NULLS LAST, amount DESC
                LIMIT ${idx} OFFSET ${idx+1}""",
            *params, limit, offset,
        )
        return {"total": total, "items": [dict(r) for r in rows]}


@router.get("/runs/{run_id}/explanations")
async def get_explanations(
    run_id: str,
    entity_type: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Get explanations for a reconciliation run."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        where = ["run_id = $1"]
        params = [run_id]
        idx = 2
        if entity_type:
            where.append(f"entity_type = ${idx}")
            params.append(entity_type)
            idx += 1

        w = " AND ".join(where)
        total = await conn.fetchval(
            f"SELECT count(*) FROM accounting.reconciliation_explanation WHERE {w}",
            *params,
        )
        rows = await conn.fetch(
            f"""SELECT * FROM accounting.reconciliation_explanation
                WHERE {w}
                ORDER BY created_at DESC
                LIMIT ${idx} OFFSET ${idx+1}""",
            *params, limit, offset,
        )
        return {"total": total, "items": [dict(r) for r in rows]}


@router.post("/runs/{run_id}/close")
async def close_run(run_id: str):
    """Close a reconciliation run (append-only)."""
    ok = await ReconciliationEngine.close_run(run_id)
    if not ok:
        raise HTTPException(status_code=400, detail="Run not found or already closed")
    return {"status": "closed", "run_id": run_id}
