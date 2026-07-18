"""Reversal service — immutable correction via full reversal posting."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any

from backend.accounting.db.pool import get_pool


async def reverse_entry(entry_id: str, reason: str = "manual reversal") -> dict[str, Any]:
    """Create a full reversal of a ledger entry.

    Returns the new (reversal) entry details.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        # 1. Load original entry
        entry = await conn.fetchrow(
            "SELECT * FROM accounting.ledger_entry WHERE id = $1",
            entry_id,
        )
        if not entry:
            raise ValueError(f"Ledger entry {entry_id} not found")
        if entry["is_reversal"]:
            raise ValueError(f"Cannot reverse a reversal entry {entry_id}")

        # 2. Load lines
        lines = await conn.fetch(
            "SELECT * FROM accounting.ledger_line WHERE entry_id = $1 ORDER BY created_at",
            entry_id,
        )

        # 3. Create reversal batch + entry
        rev_batch_id = str(uuid.uuid4())
        rev_entry_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        await conn.execute(
            """INSERT INTO accounting.posting_batch
               (id, company_id, posting_rules_version, status, total_debit, total_credit, is_closed, created_at)
               VALUES ($1,$2,'reversal','completed',$3,$4,false,now())""",
            rev_batch_id,
            entry["company_id"],
            sum(l["amount"] for l in lines if l["direction"] == "credit"),
            sum(l["amount"] for l in lines if l["direction"] == "debit"),
        )

        await conn.execute(
            """INSERT INTO accounting.ledger_entry
               (id, batch_id, company_id, period_id, entry_date, description,
                is_reversal, reversed_entry_id, posting_hash, created_by, trace_id, created_at)
               VALUES ($1,$2,$3,$4,$5,$6,true,$7,$8,$9,$10,now())""",
            rev_entry_id, rev_batch_id, entry["company_id"], entry["period_id"],
            entry["entry_date"],
            f"Reversal of {entry_id}: {reason}",
            entry_id, entry["posting_hash"], entry["created_by"], entry["trace_id"],
        )

        # 4. Reverse each line
        for line in lines:
            rev_direction = "credit" if line["direction"] == "debit" else "debit"
            await conn.execute(
                """INSERT INTO accounting.ledger_line
                   (id, entry_id, account_code, direction, amount, currency, created_at)
                   VALUES ($1,$2,$3,$4,$5,$6,now())""",
                str(uuid.uuid4()), rev_entry_id, line["account_code"],
                rev_direction, line["amount"], line["currency"],
            )

        return {
            "reversal_entry_id": rev_entry_id,
            "reversed_entry_id": entry_id,
            "lines_count": len(lines),
        }
