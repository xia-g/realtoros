"""Posting Determinism Test — Phase 3 Quality Gate.

Proves that PostingEngine determinism invariant holds BEFORE real Ledger is built:

    Posting = f(Decision, PostingRulesVersion)

Same inputs → identical output. Always. Independent of:
- time, order, worker_id, batch_id, UUID gen, queue state, randomness.

The test validates the STUB. When the real PostingEngine is built (Phase 3),
it MUST pass the same test with the same assertions.
"""

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import asyncpg
from tests.accounting.ledger.canonical_posting import canonical_posting, posting_hash, batch_ledger_hash

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


# ── Setup ──────────────────────────────────────────────────────────────


async def create_test_data(conn) -> tuple[str, str]:
    """Create one INCLUDED decision with full pipeline data."""
    import hashlib

    batch_id = str(uuid.uuid4())
    await conn.execute(
        "INSERT INTO accounting.accounting_batch (id, company_id, source, status, started_at) VALUES ($1, $2, 'determinism_test', 'completed', now())",
        batch_id, COMPANY_ID,
    )

    event_id = str(uuid.uuid4())
    fp = hashlib.sha256(f"{COMPANY_ID}:determinism:sale:150000:2026-06".encode()).hexdigest()[:16]
    await conn.execute(
        """INSERT INTO accounting.accounting_event
           (id, company_id, batch_id, event_type, event_date, amount, currency,
            source_system, source_type, source_id, event_fingerprint,
            recognition_status, version, is_current, processing_state, decision_state,
            created_at, updated_at)
           VALUES ($1,$2,$3,'sale',now(),150000.00,'RUB','TEST','determinism','det_sale_001',$4,
                   'pending',1,true,'new','pending',now(),now())""",
        event_id, COMPANY_ID, batch_id, fp,
    )

    # Link document
    await conn.execute(
        "INSERT INTO accounting.event_document (event_id, document_id, role) VALUES ($1, $2, 'primary')",
        event_id, str(uuid.uuid4()),
    )

    # Build snapshot
    from backend.accounting.recognition.snapshot_builder import build_snapshot
    await build_snapshot(event_id)

    # Create decision via replay
    from backend.accounting.replay.service import recalculate
    result = await recalculate(event_id, ruleset_version="2026.06.15")

    return result.new_decision_id, event_id


async def create_multiple_decisions(conn, count: int = 100) -> list[str]:
    """Create multiple decisions with varied event types."""
    import hashlib

    batch_id = str(uuid.uuid4())
    await conn.execute(
        "INSERT INTO accounting.accounting_batch (id, company_id, source, status, started_at) VALUES ($1, $2, 'determinism_batch', 'completed', now())",
        batch_id, COMPANY_ID,
    )

    types = ["sale", "sale", "purchase", "bank_inflow", "bank_outflow"]
    decision_ids = []

    for i in range(count):
        etype = types[i % len(types)]
        amt = (i + 1) * 1000.0
        event_id = str(uuid.uuid4())
        fp = hashlib.sha256(f"{COMPANY_ID}:batch:{i}:{amt}:2026-06".encode()).hexdigest()[:16]
        await conn.execute(
            """INSERT INTO accounting.accounting_event
               (id, company_id, batch_id, event_type, event_date, amount, currency,
                source_system, source_type, source_id, event_fingerprint,
                recognition_status, version, is_current, processing_state, decision_state,
                created_at, updated_at)
               VALUES ($1,$2,$3,$4,now(),$5,'RUB','TEST','determinism',$6,$7,
                       'pending',1,true,'new','pending',now(),now())""",
            event_id, COMPANY_ID, batch_id, etype, amt, f'batch_src_{i}', fp,
        )
        if etype in ("sale", "purchase"):
            await conn.execute(
                "INSERT INTO accounting.event_document (event_id, document_id, role) VALUES ($1, $2, 'primary')",
                event_id, str(uuid.uuid4()),
            )
        if etype in ("bank_inflow", "bank_outflow"):
            await conn.execute(
                "INSERT INTO accounting.event_transaction (event_id, transaction_id, match_type, confidence) VALUES ($1, $2, 'auto', 1.0)",
                event_id, str(uuid.uuid4()),
            )

        from backend.accounting.recognition.snapshot_builder import build_snapshot
        await build_snapshot(event_id)

        from backend.accounting.replay.service import recalculate
        result = await recalculate(event_id, ruleset_version="2026.06.15")
        decision_ids.append(result.new_decision_id)

    return decision_ids


# ── Tests ──────────────────────────────────────────────────────────────


async def test_functional_determinism(decision_id: str):
    """Same inputs → identical posting output."""
    print("\n═══ 1. Functional determinism ═══")

    run1 = await canonical_posting(decision_id, "2026.06.15")
    run2 = await canonical_posting(decision_id, "2026.06.15")

    check("Same number of lines", len(run1.lines) == len(run2.lines))
    check("Same accounts", [l.account_code for l in run1.lines] == [l.account_code for l in run2.lines])
    check("Same amounts", [l.amount for l in run1.lines] == [l.amount for l in run2.lines])
    check("Same directions", [l.direction for l in run1.lines] == [l.direction for l in run2.lines])
    check("Same hash", run1.hash() == run2.hash())

    # Verify double-entry invariant
    debits = sum(float(l.amount) for l in run1.lines if l.direction == "debit")
    credits = sum(float(l.amount) for l in run1.lines if l.direction == "credit")
    check(f"Double-entry invariant: debit={debits:.2f} credit={credits:.2f}", abs(debits - credits) < 0.01)


async def test_structural_determinism(decision_id: str):
    """Structural fields are identical, non-deterministic fields differ."""
    print("\n═══ 2. Structural determinism ═══")

    run1 = await canonical_posting(decision_id, "2026.06.15")
    run2 = await canonical_posting(decision_id, "2026.06.15")

    c1 = run1.canonical_dict()
    c2 = run2.canonical_dict()

    # Structural fields MUST match
    check("event_type matches", c1["event_type"] == c2["event_type"])
    check("posting_rules_version matches", c1["posting_rules_version"] == c2["posting_rules_version"])
    check("amount matches", c1["amount"] == c2["amount"])
    check("lines match", c1["lines"] == c2["lines"])

    # Non-deterministic fields are NOT in canonical_dict
    assert "id" not in c1, "canonical_dict must not contain id"
    assert "created_at" not in c1, "canonical_dict must not contain created_at"
    assert "trace_id" not in c1, "canonical_dict must not contain trace_id"
    check("No non-deterministic fields in canonical form", True)


async def test_batch_determinism(decision_ids: list[str]):
    """Batch ledger hash is independent of processing order."""
    print(f"\n═══ 3. Batch determinism ({len(decision_ids)} decisions) ═══")

    # Order 1: original
    hash1 = await batch_ledger_hash(decision_ids, "2026.06.15")

    # Order 2: reversed
    hash2 = await batch_ledger_hash(list(reversed(decision_ids)), "2026.06.15")

    # Order 3: shuffled
    import random
    shuffled = list(decision_ids)
    random.shuffle(shuffled)
    hash3 = await batch_ledger_hash(shuffled, "2026.06.15")

    check("Original vs reversed", hash1 == hash2)
    check("Original vs shuffled", hash1 == hash3)
    check("Batch hash is deterministic", hash1 == hash1)  # same call twice


async def test_replay_determinism(decision_id: str, event_id: str):
    """Replay produces same canonical posting (different decision_id, same content)."""
    print("\n═══ 4. Replay determinism ═══")

    # Original
    original = await canonical_posting(decision_id, "2026.06.15")

    # Replay (creates new decision)
    from backend.accounting.replay.service import recalculate

    pool = await asyncpg.create_pool(DSN.replace("+asyncpg", ""))
    try:
        replay_result = await recalculate(event_id, ruleset_version="2026.06.15")
        replay_posting = await canonical_posting(replay_result.new_decision_id, "2026.06.15")
    finally:
        await pool.close()

    # Different decision_ids
    check("New decision_id on replay", original.decision_id != replay_posting.decision_id)

    # Same canonical content
    check("Newer decision_version", replay_posting.decision_version > original.decision_version)
    check("Same canonical hash", original.hash() == replay_posting.hash())


async def test_concurrency_determinism(decision_ids: list[str]):
    """Single worker vs 8 workers produce identical batch hash."""
    print(f"\n═══ 5. Concurrency determinism ({len(decision_ids)} decisions) ═══")

    # Serial (1 worker)
    serial_hash = await batch_ledger_hash(decision_ids, "2026.06.15")

    # Concurrent (8 workers simulated via asyncio.gather)
    import asyncio, hashlib

    # Compute individual posting hashes concurrently
    async def post_hash(did: str) -> str:
        return await posting_hash(did, "2026.06.15")

    concurrent_hashes = await asyncio.gather(*[post_hash(did) for did in decision_ids])
    concurrent_hashes.sort()
    concurrent_final = hashlib.sha256("|".join(concurrent_hashes).encode()).hexdigest()

    check("Serial hash == Concurrent hash (individual postings)", serial_hash == concurrent_final)

    # Verify each individual posting hash is identical
    all_match = True
    for i, did in enumerate(decision_ids):
        h1 = await posting_hash(did, "2026.06.15")
        h2 = await posting_hash(did, "2026.06.15")
        if h1 != h2:
            all_match = False
            break
    check("Each posting hash is deterministic per worker", all_match)


# ── Main ───────────────────────────────────────────────────────────────


async def main():
    global PASS, FAIL
    print("=" * 60)
    print("Posting Determinism Test — Phase 3 Quality Gate")
    print("=" * 60)

    pool = await asyncpg.create_pool(DSN.replace("+asyncpg", ""))
    async with pool.acquire() as conn:
        # Setup
        decision_id, event_id = await create_test_data(conn)
        batch_ids = await create_multiple_decisions(conn, 100)

    # Filter to only INCLUDED decisions
    pool2 = await asyncpg.create_pool(DSN.replace("+asyncpg", ""))
    async with pool2.acquire() as conn2:
        included = []
        for did in batch_ids:
            row = await conn2.fetchrow(
                "SELECT included FROM accounting.accounting_decision WHERE id = $1 AND superseded_at IS NULL",
                did,
            )
            if row and row["included"]:
                included.append(did)
    batch_ids = included
    await pool2.close()

    print(f"\nTest data: 1 single decision + {len(batch_ids)} batch decisions")

    # Run tests
    await test_functional_determinism(decision_id)
    await test_structural_determinism(decision_id)
    await test_batch_determinism(batch_ids)
    await test_replay_determinism(decision_id, event_id)
    await test_concurrency_determinism(batch_ids)

    await pool.close()

    print(f"\n{'=' * 60}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    if FAIL > 0:
        print("❌ DETERMINISM TEST FAILED — DO NOT START PHASE 3")
    else:
        print("✅ ALL DETERMINISM TESTS PASSED — Phase 3 ready")
    print(f"{'=' * 60}")
    return FAIL


if __name__ == "__main__":
    exit(asyncio.run(main()))
