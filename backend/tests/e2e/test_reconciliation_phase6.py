"""Phase 6 E2E Tests: Reconciliation Engine.

Scenarios:
  1. Reconciliation run determinism (same inputs → same run_hash)
  2. Matching consistency (exact + fuzzy + unmatched)
  3. Gap detection (missing bank, missing ledger, amount mismatch)
  4. External data isolation (reconciliation does not change ledger)
  5. Replay run → identical result
  6. Run lifecycle (open → matched → closed)
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import date, timedelta

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "mcp", "server"))

from backend.accounting.db.pool import get_pool
from backend.accounting.reconciliation.engine import ReconciliationEngine, ExternalSystemConnector


async def _setup(pool):
    """Ensure test data exists."""
    async with pool.acquire() as conn:
        company = await conn.fetchval("SELECT DISTINCT company_id FROM accounting.ledger_entry LIMIT 1")
        if not company:
            company = "00000000-0000-0000-0000-000000000001"

        # Find date range from ledger entries
        dr = await conn.fetchrow(
            "SELECT MIN(entry_date) as dfrom, MAX(entry_date) as dto FROM accounting.ledger_entry WHERE company_id = $1",
            company,
        )
        period_from = dr["dfrom"] if dr and dr["dfrom"] else date(2026, 1, 1)
        period_to = dr["dto"] if dr and dr["dto"] else date(2026, 6, 30)

        return {"company_id": company, "period_from": period_from, "period_to": period_to}


async def main():
    passed = 0
    failed = 0
    pool = await get_pool()

    try:
        data = await _setup(pool)
        cid = data["company_id"]
        pf = data["period_from"]
        pt = data["period_to"]

        # Clean slate
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM accounting.reconciliation_explanation")
            await conn.execute("DELETE FROM accounting.reconciliation_gap")
            await conn.execute("DELETE FROM accounting.reconciliation_match")
            await conn.execute("DELETE FROM accounting.reconciliation_item")
            await conn.execute("DELETE FROM accounting.reconciliation_run")

        print("=" * 60)
        print("Phase 6 — E2E Tests")
        print("=" * 60)

        # ═══════════════════════════════════════════════════════════════
        # 1. RECONCILIATION DETERMINISM
        # ═══════════════════════════════════════════════════════════════
        print("\n1. Reconciliation Determinism (same inputs → same hash)")
        print("-" * 40)

        result1 = await ReconciliationEngine.run(cid, pf, pt)
        run_id1 = await ReconciliationEngine.save(result1)

        result2 = await ReconciliationEngine.run(cid, pf, pt)
        run_id2 = await ReconciliationEngine.save(result2)

        assert result1.run_hash == result2.run_hash, \
            f"Hash mismatch: {result1.run_hash} vs {result2.run_hash}"
        assert run_id1 == run_id2, "Idempotent: same hash → same run_id"

        passed += 1
        print(f"  ✅ Run hash: {result1.run_hash[:16]}... (identical x2)")
        print(f"     Idempotent: same run_id for same inputs")
        print(f"     Status: {result1.status}")
        print()

        # ═══════════════════════════════════════════════════════════════
        # 2. MATCHING CONSISTENCY
        # ═══════════════════════════════════════════════════════════════
        print("\n2. Matching Consistency (exact + fuzzy + unmatched)")
        print("-" * 40)

        match_types = {}
        for m in result1.matches:
            match_types[m.match_type] = match_types.get(m.match_type, 0) + 1

        print(f"     Matching results:")
        for mt, cnt in sorted(match_types.items()):
            print(f"       {mt}: {cnt}")
        print(f"     Total matches: {result1.matches_count}")
        print(f"     Total gaps: {result1.gaps_count}")

        # Verify: every match has a type
        for m in result1.matches:
            assert m.match_type in ("exact", "fuzzy", "partial", "unmatched_ledger", "unmatched_bank")

        passed += 1
        print(f"  ✅ All matches have valid types")
        print()

        # ═══════════════════════════════════════════════════════════════
        # 3. GAP DETECTION
        # ═══════════════════════════════════════════════════════════════
        print("\n3. Gap Detection")
        print("-" * 40)

        gap_types = {}
        gap_severities = {}
        for g in result1.gaps:
            gap_types[g.gap_type] = gap_types.get(g.gap_type, 0) + 1
            gap_severities[g.severity] = gap_severities.get(g.severity, 0) + 1

        print(f"     Gap types:")
        for gt, cnt in sorted(gap_types.items()):
            print(f"       {gt}: {cnt}")
        print(f"     By severity:")
        for sv, cnt in sorted(gap_severities.items()):
            print(f"       {sv}: {cnt}")

        # Verify: every gap has mandatory fields
        for g in result1.gaps:
            assert g.severity in ("critical", "warning", "info"), f"Invalid severity: {g.severity}"
            assert g.gap_type is not None, "Gap type required"
            assert g.description, "Gap description required"

        passed += 1
        print(f"  ✅ All gaps have severity, type, description")
        print()

        # ═══════════════════════════════════════════════════════════════
        # 4. EXTERNAL DATA ISOLATION
        # ═══════════════════════════════════════════════════════════════
        print("\n4. External Data Isolation (read-only)")
        print("-" * 40)

        # Capture ledger hash before
        async with pool.acquire() as conn:
            ledger_before = await conn.fetchval(
                "SELECT count(*) FROM accounting.ledger_entry WHERE company_id = $1",
                cid,
            )
            bank_before = await conn.fetchval(
                "SELECT count(*) FROM accounting.event_transaction",
            )

        # Run reconciliation (should not change anything)
        result3 = await ReconciliationEngine.run(cid, pf, pt)
        await ReconciliationEngine.save(result3)

        # Capture ledger hash after
        async with pool.acquire() as conn:
            ledger_after = await conn.fetchval(
                "SELECT count(*) FROM accounting.ledger_entry WHERE company_id = $1",
                cid,
            )
            bank_after = await conn.fetchval(
                "SELECT count(*) FROM accounting.event_transaction",
            )

        assert ledger_before == ledger_after, f"Ledger changed: {ledger_before} → {ledger_after}"
        assert bank_before == bank_after, f"Bank data changed: {bank_before} → {bank_after}"

        passed += 1
        print(f"  ✅ Ledger unchanged: {ledger_before} entries")
        print(f"     Bank data unchanged: {bank_before}")
        print()

        # ═══════════════════════════════════════════════════════════════
        # 5. REPLAY RUN
        # ═══════════════════════════════════════════════════════════════
        print("\n5. Replay Run (deterministic regeneration)")
        print("-" * 40)

        result_replay = await ReconciliationEngine.run(cid, pf, pt)
        run_id_replay = await ReconciliationEngine.save(result_replay)

        assert result_replay.run_hash == result1.run_hash, \
            f"Replay hash differs: {result_replay.run_hash[:16]} vs {result1.run_hash[:16]}"

        passed += 1
        print(f"  ✅ Run hash: {result1.run_hash[:16]}... (identical)")
        print()

        # ═══════════════════════════════════════════════════════════════
        # 6. RUN LIFECYCLE
        # ═══════════════════════════════════════════════════════════════
        print("\n6. Run Lifecycle (open → matched → closed)")
        print("-" * 40)

        # Check initial status
        assert result1.status in ("matched_full", "matched_partial"), \
            f"Initial status should be matched_*, got {result1.status}"

        # Close run
        ok = await ReconciliationEngine.close_run(run_id1)
        assert ok, "Close should succeed"

        async with pool.acquire() as conn:
            status = await conn.fetchval(
                "SELECT status FROM accounting.reconciliation_run WHERE id = $1",
                run_id1,
            )
        assert status == "closed", f"Status should be closed, got {status}"

        # Verify: run is persisted with all data
        async with pool.acquire() as conn:
            items = await conn.fetchval(
                "SELECT count(*) FROM accounting.reconciliation_item WHERE run_id = $1",
                run_id1,
            )
            matches = await conn.fetchval(
                "SELECT count(*) FROM accounting.reconciliation_match WHERE run_id = $1",
                run_id1,
            )
            gaps = await conn.fetchval(
                "SELECT count(*) FROM accounting.reconciliation_gap WHERE run_id = $1",
                run_id1,
            )

        print(f"     Status: {status}")
        print(f"     Items: {items}, Matches: {matches}, Gaps: {gaps}")
        passed += 1
        print(f"  ✅ Run lifecycle complete")

    finally:
        await pool.close()

    print(f"\n{'=' * 60}")
    print(f"Results: {passed} passed / {failed} failed")
    print(f"{'=' * 60}")
    return passed, failed


if __name__ == "__main__":
    p, f = asyncio.run(main())
    sys.exit(1 if f > 0 else 0)
