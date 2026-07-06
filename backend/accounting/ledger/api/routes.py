"""Ledger API routes for Phase 3."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.accounting.db.pool import get_pool
from backend.accounting.ledger.chart.accounts import ACCOUNTS
from backend.accounting.ledger.reversal import reverse_entry
from backend.accounting.ledger.period import close_period, lock_period, open_period
from backend.accounting.ledger.replay import recalculate as posting_replay
from backend.accounting.ledger.posting.engine import PostingEngine

router = APIRouter(prefix="/ledger", tags=["Ledger"])


@router.get("/accounts")
async def list_accounts():
    """List chart of accounts."""
    return {"accounts": [{"code": a.code, "name": a.name, "type": a.acct_type} for a in ACCOUNTS]}


@router.post("/post")
async def post_decision(body: dict):
    """Post a single decision to the ledger."""
    decision_id = body.get("decision_id")
    if not decision_id:
        raise HTTPException(status_code=400, detail="decision_id required")

    company_id = body.get("company_id")
    if not company_id:
        raise HTTPException(status_code=400, detail="company_id required")

    rules_version = body.get("posting_rules_version", "2026.06.15")
    engine = PostingEngine()
    await engine.seed_chart()

    try:
        result = await engine.evaluate(decision_id, rules_version, company_id)
        return {
            "batch_id": result.batch_id,
            "entry_id": result.entry_id,
            "posting_hash": result.posting_hash,
            "lines": result.lines,
            "total_debit": result.total_debit,
            "total_credit": result.total_credit,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/entries")
async def list_entries(
    company_id: str | None = None,
    period_id: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List ledger entries."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        where = ["1=1"]
        params = []
        idx = 1
        if company_id:
            where.append(f"company_id = ${idx}")
            params.append(company_id)
            idx += 1
        if period_id:
            where.append(f"period_id = ${idx}")
            params.append(period_id)
            idx += 1

        w = " AND ".join(where)
        total = await conn.fetchval(f"SELECT count(*) FROM accounting.ledger_entry WHERE {w}", *params)
        rows = await conn.fetch(
            f"""SELECT id, batch_id, company_id, period_id, entry_date, description,
                      is_reversal, reversed_entry_id, posting_hash, created_by, trace_id, created_at
               FROM accounting.ledger_entry WHERE {w}
               ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx+1}""",
            *params, limit, offset,
        )
        return {"total": total, "items": [dict(r) for r in rows]}


@router.get("/entries/{entry_id}")
async def get_entry(entry_id: str):
    """Get ledger entry with its lines."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        entry = await conn.fetchrow(
            "SELECT * FROM accounting.ledger_entry WHERE id = $1",
            entry_id,
        )
        if not entry:
            raise HTTPException(status_code=404, detail="Entry not found")

        lines = await conn.fetch(
            "SELECT * FROM accounting.ledger_line WHERE entry_id = $1",
            entry_id,
        )
        return {"entry": dict(entry), "lines": [dict(l) for l in lines]}


@router.post("/reverse")
async def reverse(body: dict):
    """Reverse a ledger entry."""
    entry_id = body.get("entry_id")
    reason = body.get("reason", "manual reversal")
    if not entry_id:
        raise HTTPException(status_code=400, detail="entry_id required")
    try:
        result = await reverse_entry(entry_id, reason)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/period/{period_id}/close")
async def period_close(period_id: str):
    """Close a period."""
    ok = await close_period(period_id)
    if not ok:
        raise HTTPException(status_code=400, detail="Period not found or already closed")
    return {"status": "closed", "period_id": period_id}


@router.post("/period/{period_id}/open")
async def period_open(period_id: str):
    """Open a period."""
    ok = await open_period(period_id)
    if not ok:
        raise HTTPException(status_code=400, detail="Period not found or already open")
    return {"status": "open", "period_id": period_id}


@router.post("/replay")
async def replay(body: dict):
    """Recalculate a posting for a replayed decision."""
    decision_id = body.get("decision_id")
    company_id = body.get("company_id")
    if not decision_id or not company_id:
        raise HTTPException(status_code=400, detail="decision_id and company_id required")

    rules_version = body.get("posting_rules_version", "2026.06.15")
    try:
        result = await posting_replay(decision_id, rules_version, company_id)
        return {
            "new_batch_id": result.new_batch_id,
            "new_entry_id": result.new_entry_id,
            "old_entry_id": result.old_entry_id,
            "is_delta": result.is_delta,
            "delta_amount": result.delta_amount,
            "diff": result.diff,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
