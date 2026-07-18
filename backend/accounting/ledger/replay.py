"""Posting Replay — recalculate posting for a replayed decision.

Invariant: old postings are preserved, new ones are created.
In closed period: creates delta posting to current open period.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.accounting.db.pool import get_pool
from backend.accounting.ledger.posting.engine import PostingEngine
from backend.accounting.ledger.period import find_open_period, is_period_closed


@dataclass
class PostingReplayResult:
    new_batch_id: str
    new_entry_id: str
    old_entry_id: str | None
    is_delta: bool
    delta_amount: float | None = None
    diff: list[str] = field(default_factory=list)


async def recalculate(
    decision_id: str,
    posting_rules_version: str,
    company_id: str,
    trace_id: str | None = None,
) -> PostingReplayResult:
    """Recalculate posting for a decision (already replayed in Decision Engine)."""
    engine = PostingEngine()
    pool = await get_pool()

    async with pool.acquire() as conn:
        # 1. Check if this decision already has a posting
        old_batch = await conn.fetchrow(
            """SELECT pb.id, le.id AS entry_id, le.period_id, le.posting_hash, le.entry_date
               FROM accounting.posting_batch pb
               JOIN accounting.ledger_entry le ON le.batch_id = pb.id
               WHERE pb.decision_id = $1
               ORDER BY le.created_at DESC LIMIT 1""",
            decision_id,
        )
    old_entry_id = str(old_batch["entry_id"]) if old_batch else None

    # 2. Run posting engine
    result = await engine.evaluate(decision_id, posting_rules_version, company_id, trace_id)

    # 3. Check period status
    delta_amount = None
    is_delta = False
    diff: list[str] = []

    async with pool.acquire() as conn:
        if old_batch:
            period_id = old_batch["period_id"]
            if period_id:
                closed = await is_period_closed(str(period_id))
                if closed:
                    # Delta posting to current open period
                    open_period = await find_open_period(
                        company_id,
                        old_batch["entry_date"],
                    )
                    if open_period:
                        # Move posting to open period
                        await conn.execute(
                            "UPDATE accounting.ledger_entry SET period_id = $2 WHERE id = $1",
                            result.entry_id, open_period,
                        )
                        is_delta = True
                        diff.append(f"Period closed: posting moved to open period {open_period[:8]}")

                    # Calculate delta
                    new_total = result.total_debit
                    old_total = old_batch.get("total_debit", 0) if old_batch else 0
                    delta_amount = round(new_total - float(old_total), 2)

    return PostingReplayResult(
        new_batch_id=result.batch_id,
        new_entry_id=result.entry_id,
        old_entry_id=old_entry_id,
        is_delta=is_delta,
        delta_amount=delta_amount,
        diff=diff,
    )
