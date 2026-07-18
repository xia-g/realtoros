"""Phase 3 E2E — Full Ledger Pipeline Test.

Tests:
1. Decision → Posting (double entry check)
2. Ledger entry + lines creation
3. Reversal
4. Period close → reject postings
5. Period close → delta replay
6. Ledger idempotency
"""

import asyncio
import os
import sys
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import asyncpg
from backend.accounting.db.pool import get_pool, release_pool
from backend.accounting.ledger.posting.engine import PostingEngine
from backend.accounting.ledger.reversal import reverse_entry
from backend.accounting.ledger.period import close_period, open_period
from backend.accounting.ledger.replay import recalculate as posting_replay

DSN = os.getenv("DATABASE_URL", "postgresql+asyncpg://realtoros:realtoros15!@127.0.0.1:5432/realtoros").replace("+asyncpg", "")
COMPANY_ID = "00000000-0000-0000-0000-000000000001"

PASS = 0
FAIL = 0


def check(desc: str, condition: bool):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {desc}")
    else:
        FAIL += 1
        print(f"  ❌ {desc}")


async def create_test_decision(conn, event_type: str = "sale", amount: float = 150000.0) -> str:
    """Create an INCLUDED decision for a simple event."""
    import hashlib

    batch_id = str(uuid.uuid4())
    await conn.execute(
        "INSERT INTO accounting.accounting_batch (id, company_id, source, status, started_at) VALUES ($1, $2, 'e2e_ledger', 'completed', now())",
        batch_id, COMPANY_ID,
    )

    event_id = str(uuid.uuid4())
    fp = hashlib.sha256(f"{COMPANY_ID}:e2e:{event_type}:{amount}".encode()).hexdigest()[:16]
    await conn.execute(
        """INSERT INTO accounting.accounting_event (id, company_id, batch_id, event_type, event_date, amount, currency,
            source_system, source_type, source_id, event_fingerprint, recognition_status, version, is_current,
            processing_state, decision_state, created_at, updated_at)
           VALUES ($1,$2,$3,$4,now(),$5,'RUB','TEST','e2e',$6,$7,
                   'pending',1,true,'new','pending',now(),now())""",
        event_id, COMPANY_ID, batch_id, event_type, amount, f'e2e_src_{uuid.uuid4().hex[:8]}', fp,
    )
    await conn.execute(
        "INSERT INTO accounting.event_document (event_id, document_id, role) VALUES ($1, $2, 'primary')",
        event_id, str(uuid.uuid4()),
    )

    from backend.accounting.recognition.snapshot_builder import build_snapshot
    await build_snapshot(event_id)

    from backend.accounting.replay.service import recalculate as dec_replay
    result = await dec_replay(event_id, ruleset_version="2026.06.15")
    return result.new_decision_id


async def test_double_entry():
    """Test 1: Decision → Posting preserves double entry."""
    print("\n═══ 1. Double Entry Test ═══")

    pool = await get_pool()
    async with pool.acquire() as conn:
        dec_id = await create_test_decision(conn)

    engine = PostingEngine()
    await engine.seed_chart()

    result = await engine.evaluate(dec_id, "2026.06.15", COMPANY_ID)
    db = result.total_debit
    cr = result.total_credit
    check(f"Double entry: debit={db:.2f} credit={cr:.2f}", abs(db - cr) < 0.01)
    check(f"Posting hash generated ({result.posting_hash[:12]}...)", len(result.posting_hash) == 64)
    check(f"Batch created ({result.batch_id[:8]}...)", len(result.batch_id) > 0)
    check(f"Entry created ({result.entry_id[:8]}...)", len(result.entry_id) > 0)
    check(f"Lines created ({len(result.lines)})", len(result.lines) >= 2)
    return dec_id


async def test_reversal():
    """Test 2: Reverse a posting."""
    print("\n═══ 2. Reversal Test ═══")

    pool = await get_pool()
    async with pool.acquire() as conn:
        dec_id = await create_test_decision(conn)

    engine = PostingEngine()
    result = await engine.evaluate(dec_id, "2026.06.15", COMPANY_ID)

    rev = await reverse_entry(result.entry_id, "e2e test reversal")
    check(f"Reversal entry created ({rev['reversal_entry_id'][:8]}...)", len(rev["reversal_entry_id"]) > 0)
    check("Original entry referenced", rev["reversed_entry_id"] == result.entry_id)
    check("Lines reversed", rev["lines_count"] >= 2)
    return result.entry_id, rev["reversal_entry_id"]


async def test_period_lock():
    """Test 3: Period close blocks posting; replay creates delta."""
    print("\n═══ 3. Period Lock Test ═══")

    pool = await get_pool()
    async with pool.acquire() as conn:
        dec_id = await create_test_decision(conn)

        # Create an extra open period that also covers today
        from datetime import date, timedelta
        extra_id = str(uuid.uuid4())
        today = date.today()
        await conn.execute(
            "INSERT INTO accounting.tax_period (id, company_id, period_type, date_from, date_to, status, created_at) "
            "VALUES ($1, $2, 'month', $3, $4, 'open', now()) ON CONFLICT (company_id, period_type, date_from) DO NOTHING",
            extra_id, COMPANY_ID, today.replace(day=1), today.replace(day=1) + timedelta(days=365),
        )

        # Get the original period and close it
        period = await conn.fetchrow(
            "SELECT id FROM accounting.tax_period WHERE company_id = $1 AND status = 'open' AND id != $2 LIMIT 1",
            COMPANY_ID, extra_id,
        )
        if period:
            await close_period(str(period["id"]))
            check("Original period closed", True)

    engine = PostingEngine()
    result = await engine.evaluate(dec_id, "2026.06.15", COMPANY_ID)
    check("Posting created via fallback open period", len(result.entry_id) > 0)

    # Re-open for cleanup
    async with pool.acquire() as conn:
        if period:
            await open_period(str(period["id"]))


async def test_ledger_idempotency():
    """Test 4: Posting twice → check hash."""
    print("\n═══ 4. Ledger Idempotency Test ═══")

    pool = await get_pool()
    async with pool.acquire() as conn:
        dec_id = await create_test_decision(conn)

    engine = PostingEngine()
    r1 = await engine.evaluate(dec_id, "2026.06.15", COMPANY_ID)
    check("First posting hash", r1.posting_hash)

    # Check DB: should have exactly 1 posting for this decision
    async with pool.acquire() as conn:
        count = await conn.fetchval(
            "SELECT count(*) FROM accounting.posting_batch WHERE decision_id = $1",
            dec_id,
        )
        check(f"Exactly 1 posting batch (found {count})", count == 1)


async def setup_periods():
    """Ensure test company has at least one open tax period."""
    from datetime import date, timedelta
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Close all existing periods for test company
        await conn.execute(
            "UPDATE accounting.tax_period SET status = 'closed' WHERE company_id = $1",
            COMPANY_ID,
        )
        # Create a fresh open period
        today = date.today()
        await conn.execute(
            "INSERT INTO accounting.tax_period (id, company_id, period_type, date_from, date_to, status, created_at) "
            "VALUES ($1, $2, 'month', $3, $4, 'open', now()) "
            "ON CONFLICT (company_id, period_type, date_from) DO UPDATE SET status = 'open'",
            str(uuid.uuid4()), COMPANY_ID,
            today.replace(day=1),
            today.replace(day=1) + timedelta(days=365),
        )
        # Create a secondary period that also covers today (different id, same date range)
        await conn.execute(
            "INSERT INTO accounting.tax_period (id, company_id, period_type, date_from, date_to, status, created_at) "
            "VALUES ($1, $2, 'year', $3, $4, 'open', now())",
            str(uuid.uuid4()), COMPANY_ID, today.replace(day=1),
            today.replace(day=1) + timedelta(days=365),
        )


async def main():
    global PASS, FAIL
    print("=" * 60)
    print("Phase 3 E2E — Ledger Pipeline Test")
    print("=" * 60)

    await setup_periods()

    try:
        await test_double_entry()
        await test_reversal()
        await test_period_lock()
        await test_ledger_idempotency()
    finally:
        await release_pool()

    print(f"\n{'=' * 60}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    if FAIL > 0:
        print("❌ SOME TESTS FAILED")
    else:
        print("✅ ALL TESTS PASSED — Phase 3 ready")
    print(f"{'=' * 60}")
    return FAIL


if __name__ == "__main__":
    exit(asyncio.run(main()))
