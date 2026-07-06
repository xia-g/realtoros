"""Tax API routes for Phase 4."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query

from backend.accounting.db.pool import get_pool
from backend.accounting.models.enums import TaxRegisterType
from backend.accounting.tax.policy import TaxPolicy
from backend.accounting.tax.assignment import TaxAssignmentEngine
from backend.accounting.tax.register import TaxRegister
from backend.accounting.tax.replay import TaxReplay
from backend.accounting.tax.period import TaxPeriodResolver
from backend.accounting.tax.explain import TaxExplainer
from backend.accounting.tax.optimize_routes import router as optimize_router

router = APIRouter(prefix="/tax", tags=["Tax"])

router.include_router(optimize_router, prefix="", tags=["Tax Optimization"])


# ── Policies ───────────────────────────────────────────────────────────


@router.get("/policies")
async def list_policies(
    is_active: bool | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List tax policies with their versions."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        where = ["1=1"]
        params = []
        idx = 1
        if is_active is not None:
            where.append(f"p.is_active = ${idx}")
            params.append(is_active)
            idx += 1

        w = " AND ".join(where)
        total = await conn.fetchval(
            f"SELECT count(*) FROM accounting.tax_policy p WHERE {w}",
            *params,
        )
        rows = await conn.fetch(
            f"""SELECT p.id, p.name, p.description, p.tax_regime, p.is_active,
                       pv.id AS version_id, pv.version, pv.effective_from,
                       pv.effective_to, pv.rules_hash, pv.is_active AS version_active
                FROM accounting.tax_policy p
                LEFT JOIN accounting.tax_policy_version pv ON pv.policy_id = p.id
                WHERE {w}
                ORDER BY p.name, pv.effective_from DESC
                LIMIT ${idx} OFFSET ${idx+1}""",
            *params, limit, offset,
        )

        # Group by policy
        policies: dict = {}
        for r in rows:
            pid = str(r["id"])
            if pid not in policies:
                policies[pid] = {
                    "id": pid,
                    "name": r["name"],
                    "description": r["description"],
                    "tax_regime": r["tax_regime"],
                    "is_active": r["is_active"],
                    "versions": [],
                }
            if r["version_id"]:
                policies[pid]["versions"].append({
                    "id": str(r["version_id"]),
                    "version": r["version"],
                    "effective_from": str(r["effective_from"]),
                    "effective_to": str(r["effective_to"]) if r["effective_to"] else None,
                    "rules_hash": r["rules_hash"],
                    "is_active": r["version_active"],
                })

        return {"total": total, "items": list(policies.values())}


# ── Assignments ────────────────────────────────────────────────────────


@router.get("/assignments")
async def list_assignments(
    company_id: str | None = None,
    ledger_line_id: str | None = None,
    register_type: str | None = None,
    is_current: bool | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List tax assignments with filters."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        where = ["1=1"]
        params = []
        idx = 1

        if company_id:
            where.append(f"company_id = ${idx}")
            params.append(company_id)
            idx += 1
        if ledger_line_id:
            where.append(f"ledger_line_id = ${idx}")
            params.append(ledger_line_id)
            idx += 1
        if register_type:
            where.append(f"register_type = ${idx}")
            params.append(register_type)
            idx += 1
        if is_current is not None:
            where.append(f"is_current = ${idx}")
            params.append(is_current)
            idx += 1

        w = " AND ".join(where)
        total = await conn.fetchval(
            f"SELECT count(*) FROM accounting.tax_assignment WHERE {w}",
            *params,
        )
        rows = await conn.fetch(
            f"""SELECT * FROM accounting.tax_assignment
                WHERE {w}
                ORDER BY created_at DESC
                LIMIT ${idx} OFFSET ${idx+1}""",
            *params, limit, offset,
        )
        return {"total": total, "items": [dict(r) for r in rows]}


@router.post("/assignments/batch")
async def assign_entry(body: dict):
    """Assign ALL ledger lines of an entry to tax registers."""
    entry_id = body.get("entry_id")
    company_id = body.get("company_id")
    if not entry_id or not company_id:
        raise HTTPException(status_code=400, detail="entry_id and company_id required")

    engine = TaxAssignmentEngine()

    # Get active policy for company
    policy = await engine._policy.get_active_policy_version(company_id)
    if not policy:
        raise HTTPException(status_code=400, detail="No active tax policy found for company")

    assignments = await engine.assign_entry_lines(
        entry_id=entry_id,
        company_id=company_id,
        policy_version=policy,
        trace_id=body.get("trace_id"),
    )
    return {
        "assignments_count": len(assignments),
        "assignments": [
            {
                "id": a.assignment_id,
                "ledger_line_id": a.ledger_line_id,
                "register_type": a.register_type,
                "tax_treatment": a.tax_treatment,
                "excluded": a.excluded,
                "reason_code": a.reason_code,
            }
            for a in assignments
        ],
    }


# ── Registers ──────────────────────────────────────────────────────────


@router.get("/registers")
async def list_registers(
    company_id: str | None = None,
    tax_period_id: str | None = None,
    register_type: str | None = None,
    is_current: bool | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List tax registers with filters."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        where = ["1=1"]
        params = []
        idx = 1

        if company_id:
            where.append(f"company_id = ${idx}")
            params.append(company_id)
            idx += 1
        if tax_period_id:
            where.append(f"tax_period_id = ${idx}")
            params.append(tax_period_id)
            idx += 1
        if register_type:
            where.append(f"register_type = ${idx}")
            params.append(register_type)
            idx += 1
        if is_current is not None:
            where.append(f"is_current = ${idx}")
            params.append(is_current)
            idx += 1

        w = " AND ".join(where)
        total = await conn.fetchval(
            f"SELECT count(*) FROM accounting.tax_register WHERE {w}",
            *params,
        )
        rows = await conn.fetch(
            f"""SELECT * FROM accounting.tax_register
                WHERE {w}
                ORDER BY register_version DESC
                LIMIT ${idx} OFFSET ${idx+1}""",
            *params, limit, offset,
        )
        return {"total": total, "items": [dict(r) for r in rows]}


@router.get("/registers/{register_id}")
async def get_register(register_id: str):
    """Get a tax register with all its entries."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        reg = await conn.fetchrow(
            "SELECT * FROM accounting.tax_register WHERE id = $1",
            register_id,
        )
        if not reg:
            raise HTTPException(status_code=404, detail="Register not found")

        entries = await conn.fetch(
            """SELECT tre.*, ll.account_code, ll.direction, ll.amount
               FROM accounting.tax_register_entry tre
               JOIN accounting.ledger_line ll ON ll.id = tre.ledger_line_id
               WHERE tre.register_id = $1
               ORDER BY tre.created_at""",
            register_id,
        )

        return {
            "register": dict(reg),
            "entries": [dict(e) for e in entries],
        }


@router.post("/registers/generate")
async def generate_registers(body: dict):
    """Generate tax registers for a period from existing assignments."""
    company_id = body.get("company_id")
    tax_period_id = body.get("tax_period_id")
    if not company_id or not tax_period_id:
        raise HTTPException(status_code=400, detail="company_id and tax_period_id required")

    pool = await get_pool()
    async with pool.acquire() as conn:
        assignments = await conn.fetch(
            """SELECT ta.* FROM accounting.tax_assignment ta
               JOIN accounting.ledger_entry le ON le.id = ta.ledger_entry_id
               WHERE le.company_id = $1 AND le.period_id = $2
                 AND ta.is_current = true""",
            company_id,
            tax_period_id,
        )

        if not assignments:
            raise HTTPException(status_code=404, detail="No current assignments found for this period")

        # Get policy version from first assignment
        first = assignments[0]
        policy_version_id = first["policy_version_id"]

    results = await TaxRegister.generate_all(
        assignments=[dict(a) for a in assignments],
        company_id=company_id,
        tax_period_id=tax_period_id,
        policy_version_id=str(policy_version_id) if policy_version_id else "",
    )

    return {
        "registers_created": list(results.keys()),
        "details": {
            rt: {
                "register_id": r.register_id,
                "total_amount": r.total_amount,
                "entry_count": r.entry_count,
                "version": r.version,
            }
            for rt, r in results.items()
        },
    }


# ── Replay ─────────────────────────────────────────────────────────────


@router.post("/recalculate")
async def recalculate(body: dict):
    """Recalculate tax assignments and regenerate registers."""
    company_id = body.get("company_id")
    tax_period_id = body.get("tax_period_id")
    tax_policy_version = body.get("tax_policy_version")

    if not company_id or not tax_period_id:
        raise HTTPException(status_code=400, detail="company_id and tax_period_id required")

    replay = TaxReplay()
    try:
        result = await replay.recalculate(
            company_id=company_id,
            tax_period_id=tax_period_id,
            tax_policy_version=tax_policy_version,
            trace_id=body.get("trace_id"),
        )
        return {
            "new_assignments_count": result.new_assignments_count,
            "superseded_count": result.superseded_count,
            "registers_created": result.registers_created,
            "policy_version_used": result.policy_version_used,
            "ledger_unchanged": result.ledger_unchanged,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Periods ────────────────────────────────────────────────────────────


@router.get("/periods")
async def list_periods(
    company_id: str | None = None,
    status: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List tax periods."""
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
            f"SELECT count(*) FROM accounting.tax_period WHERE {w}",
            *params,
        )
        rows = await conn.fetch(
            f"""SELECT * FROM accounting.tax_period
                WHERE {w}
                ORDER BY date_from DESC
                LIMIT ${idx} OFFSET ${idx+1}""",
            *params, limit, offset,
        )
        return {"total": total, "items": [dict(r) for r in rows]}


@router.post("/period/close")
async def close_tax_period(body: dict):
    """Close a tax period (all checks must pass)."""
    tax_period_id = body.get("tax_period_id")
    if not tax_period_id:
        raise HTTPException(status_code=400, detail="tax_period_id required")

    check = await TaxPeriodResolver.can_close_tax_period(tax_period_id)
    if not check["can_close"]:
        raise HTTPException(status_code=400, detail=check["reason"])

    ok = await TaxPeriodResolver.close_tax_period(tax_period_id)
    if not ok:
        raise HTTPException(status_code=400, detail="Failed to close period")
    return {"status": "closed", "period_id": tax_period_id}


# ── Explanations ───────────────────────────────────────────────────────


@router.get("/explanations")
async def list_explanations(
    register_entry_id: str | None = None,
    register_id: str | None = None,
    ledger_line_id: str | None = None,
    limit: int = Query(50, ge=1, le=500),
):
    """Get tax explanations with full chain.

    Filter by register_entry_id, register_id, or ledger_line_id.
    """
    if register_entry_id:
        expl = await TaxExplainer.explain_register_entry(register_entry_id)
        if not expl:
            raise HTTPException(status_code=404, detail="Register entry not found")
        return {"explanations": [{
            "explanation_id": expl.explanation_id,
            "register_entry_id": expl.register_entry_id,
            "register_type": expl.register_type,
            "tax_treatment": expl.tax_treatment,
            "excluded": expl.excluded,
            "reason_code": expl.reason_code,
            "why_included": expl.why_included,
            "why_excluded": expl.why_excluded,
            "rule_code": expl.rule_code,
            "chain": expl.chain,
        }]}

    if register_id:
        expls = await TaxExplainer.explain_register(register_id)
        return {"total": len(expls), "explanations": [_expl_to_dict(e) for e in expls[:limit]]}

    if ledger_line_id:
        expl = await TaxExplainer.explain_by_ledger_line(ledger_line_id)
        if not expl:
            raise HTTPException(status_code=404, detail="No explanation found for this ledger line")
        return {"explanations": [_expl_to_dict(expl)]}

    # List recent explanations from DB
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT * FROM accounting.tax_explanation
               ORDER BY created_at DESC LIMIT $1""",
            limit,
        )
        return {"total": len(rows), "explanations": [dict(r) for r in rows]}


def _expl_to_dict(e):
    return {
        "explanation_id": e.explanation_id,
        "register_entry_id": e.register_entry_id,
        "register_type": e.register_type,
        "tax_treatment": e.tax_treatment,
        "excluded": e.excluded,
        "reason_code": e.reason_code,
        "why_included": e.why_included,
        "why_excluded": e.why_excluded,
        "rule_code": e.rule_code,
        "chain": e.chain,
    }


# ── Seed ───────────────────────────────────────────────────────────────


@router.post("/seed")
async def seed_tax_policies():
    """Seed default tax policies for all regimes. Idempotent."""
    result = await TaxPolicy.seed_default_policies()
    return {"seeded": result}


# ── Metrics ────────────────────────────────────────────────────────────


@router.get("/metrics")
async def get_tax_metrics():
    """Get aggregate tax metrics."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        return {
            "total_assignments": await conn.fetchval("SELECT count(*) FROM accounting.tax_assignment"),
            "current_assignments": await conn.fetchval("SELECT count(*) FROM accounting.tax_assignment WHERE is_current = true"),
            "excluded_count": await conn.fetchval("SELECT count(*) FROM accounting.tax_assignment WHERE excluded = true AND is_current = true"),
            "total_registers": await conn.fetchval("SELECT count(*) FROM accounting.tax_register"),
            "total_register_entries": await conn.fetchval("SELECT count(*) FROM accounting.tax_register_entry"),
            "policies_count": await conn.fetchval("SELECT count(*) FROM accounting.tax_policy"),
            "policy_versions_count": await conn.fetchval("SELECT count(*) FROM accounting.tax_policy_version"),
        }
