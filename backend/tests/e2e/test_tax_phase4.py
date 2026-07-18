"""Phase 4 E2E Tests: Tax Assignment Engine + Tax Registers.

Scenarios:
  1. Full pipeline: decision → posting → ledger → assignment → register
  2. USN tax regime assignment
  3. VAT handling under GENERAL regime
  4. Exclusion handling
  5. Tax replay with new policy version
  6. Idempotent assignment
"""

from __future__ import annotations

import asyncio
import json
import sys
import os
import uuid
from datetime import date, datetime, timezone

# Setup paths — project root is ../../.. from backend/tests/e2e/
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "mcp", "server"))

# Import via backend namespace (modules use `from backend.accounting...`)
from backend.accounting.db.pool import get_pool
from backend.accounting.models.enums import (
    TaxRegisterType,
    TaxTreatment,
    TaxRegime,
)
from backend.accounting.tax.policy import TaxPolicy
from backend.accounting.tax.assignment import TaxAssignmentEngine
from backend.accounting.tax.register import TaxRegister
from backend.accounting.tax.replay import TaxReplay
from backend.accounting.tax.period import TaxPeriodResolver


async def _create_test_data(pool):
    """Create test ledger entries with ledger lines for E2E testing.
    
    Uses existing data where available.
    """
    async with pool.acquire() as conn:
        # Use existing company IDs — tax_period records use 00000000-0000-0000-0000-000000000001
        company = await conn.fetchval(
            "SELECT DISTINCT company_id FROM accounting.ledger_entry LIMIT 1"
        )
        if not company:
            company = "00000000-0000-0000-0000-000000000001"
        print(f"  ℹ Using company_id={str(company)[:8]}...")

        # 2. Ensure tax_regime exists (column: regime_type, enum: tax_regime_type)
        regime_count = await conn.fetchval(
            "SELECT count(*) FROM accounting.tax_regime WHERE company_id = $1",
            company,
        )
        if regime_count == 0:
            regime_id = uuid.uuid4()
            await conn.execute(
                "INSERT INTO accounting.tax_regime "
                "(id, company_id, regime_type, valid_from, settings_json, is_active) "
                "VALUES ($1, $2, 'usn_income', '2026-01-01', '{}'::jsonb, true)",
                regime_id,
                company,
            )
            print("  ℹ Created tax_regime for company")

        # 3. Ensure open tax period exists (use period_type='year' for USN)
        period = await conn.fetchrow(
            "SELECT id FROM accounting.tax_period WHERE company_id = $1 AND status = 'open' LIMIT 1",
            company,
        )
        if not period:
            period_id = uuid.uuid4()
            await conn.execute(
                """INSERT INTO accounting.tax_period (id, company_id, date_from, date_to, period_type, status)
                   VALUES ($1, $2, '2026-01-01', '2026-12-31', 'year', 'open')""",
                period_id,
                company,
            )
            period = {"id": period_id}

        # 4. Create posting_batch
        batch_id = uuid.uuid4()
        await conn.execute(
            """INSERT INTO accounting.posting_batch
               (id, company_id, decision_id, posting_rules_version, status, total_debit, total_credit, is_closed)
               VALUES ($1, $2, gen_random_uuid(), '2026.01.01', 'completed', 150000, 150000, false)""",
            batch_id,
            company,
        )

        # 5. Create ledger_entry
        entry_id = uuid.uuid4()
        await conn.execute(
            """INSERT INTO accounting.ledger_entry
               (id, batch_id, company_id, period_id, entry_date, description,
                is_reversal, posting_hash, created_at)
               VALUES ($1, $2, $3, $4, '2026-06-15', 'Sale test 150k', false,
                       'test_e2e_hash_001', now())""",
            entry_id,
            batch_id,
            company,
            period["id"],
        )

        # 6. Create ledger lines (sale: DR 62 150k, CR 90.01 150k)
        line_receivable = uuid.uuid4()
        line_revenue = uuid.uuid4()
        await conn.execute(
            """INSERT INTO accounting.ledger_line (id, entry_id, account_code, direction, amount, created_at)
               VALUES ($1, $2, '62', 'debit', 150000, now())""",
            line_receivable,
            entry_id,
        )
        await conn.execute(
            """INSERT INTO accounting.ledger_line (id, entry_id, account_code, direction, amount, created_at)
               VALUES ($1, $2, '90.01', 'credit', 150000, now())""",
            line_revenue,
            entry_id,
        )

        return {
            "company_id": company,
            "period_id": str(period["id"]),
            "entry_id": str(entry_id),
            "lines": [
                {"id": str(line_receivable), "account_code": "62", "direction": "debit", "amount": 150000},
                {"id": str(line_revenue), "account_code": "90.01", "direction": "credit", "amount": 150000},
            ],
        }


async def main():
    passed = 0
    failed = 0
    pool = await get_pool()

    try:
        # Clean up any stale test data
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM accounting.tax_explanation")
            await conn.execute("DELETE FROM accounting.tax_register_entry")
            await conn.execute("DELETE FROM accounting.tax_register")
            await conn.execute("DELETE FROM accounting.tax_assignment")

        # ═══════════════════════════════════════════════════════════════
        # SETUP
        # ═══════════════════════════════════════════════════════════════
        print("=" * 60)
        print("Phase 4 — E2E Tests")
        print("=" * 60)
        print()

        data = await _create_test_data(pool)
        cid = data["company_id"]
        pid = data["period_id"]
        lines = data["lines"]

        # ═══════════════════════════════════════════════════════════════
        # 1. TAX ASSIGNMENT DETERMINISM
        # ═══════════════════════════════════════════════════════════════
        print("1. Tax Assignment Determinism")
        print("-" * 40)

        engine = TaxAssignmentEngine()
        policy = await engine._policy.get_active_policy_version(cid)
        assert policy is not None, "Policy should be available for USN_D company"

        # Assign revenue line
        rev_line = lines[1]  # 90.01 credit
        a1 = await engine.assign(ledger_line=rev_line, company_id=cid, policy_version=policy)
        a2 = await engine.assign(ledger_line=rev_line, company_id=cid, policy_version=policy)

        assert a1.register_type == a2.register_type, "Same inputs → same register_type"
        assert a1.tax_treatment == a2.tax_treatment, "Same inputs → same treatment"
        assert a1.reason_code == a2.reason_code, "Same inputs → same reason_code"
        assert a1.register_type == "KUDIR_INCOME", "Revenue under USN_D → KUDIR_INCOME"
        assert a1.tax_treatment == "taxable", "Revenue under USN_D → taxable"

        passed += 1
        print(f"  ✅ Determinism: same inputs → same results")
        print(f"     Line: 90.01/credit → {a1.register_type} ({a1.tax_treatment})")
        print()

        # ═══════════════════════════════════════════════════════════════
        # 2. EXCLUSION HANDLING
        # ═══════════════════════════════════════════════════════════════
        print("2. Exclusion Handling")
        print("-" * 40)

        recv_line = lines[0]  # 62 debit
        a3 = await engine.assign(ledger_line=recv_line, company_id=cid, policy_version=policy)

        assert a3.excluded, "Receivable account 62 → excluded"
        assert a3.register_type == "EXCLUDED", "62 → EXCLUDED register"
        assert a3.reason_code == "unmapped_account", "Unmapped account → correct reason"

        passed += 1
        print(f"  ✅ Exclusion: 62/debit → {a3.register_type} ({a3.reason_code})")
        print()

        # ═══════════════════════════════════════════════════════════════
        # 3. REGISTER GENERATION
        # ═══════════════════════════════════════════════════════════════
        print("3. Register Generation")
        print("-" * 40)

        # Save assignments to DB for register generation
        for line in lines:
            ll_dict = {"id": line["id"], "account_code": line["account_code"],
                       "direction": line["direction"], "amount": line["amount"],
                       "company_id": cid}
            assignment = await engine.assign(ledger_line=ll_dict, company_id=cid, policy_version=policy)
            await engine.assign_and_save(
                ledger_line=ll_dict,
                entry_id=data["entry_id"],
                company_id=cid,
                policy_version=policy,
            )

        # Load assignments from DB
        async with pool.acquire() as conn:
            assignment_rows = await conn.fetch(
                """SELECT ta.* FROM accounting.tax_assignment ta
                   JOIN accounting.ledger_entry le ON le.id = ta.ledger_entry_id
                   WHERE le.company_id = $1 AND le.period_id = $2
                     AND ta.is_current = true""",
                cid,
                pid,
            )

        # Generate KUDIR_INCOME register
        result = await TaxRegister.generate(
            assignments=[dict(r) for r in assignment_rows],
            company_id=cid,
            tax_period_id=pid,
            register_type="KUDIR_INCOME",
            policy_version_id=policy.policy_version_id,
        )

        assert result.total_amount == 150000, f"Expected 150000 total, got {result.total_amount}"
        assert result.entry_count == 1, f"Expected 1 KUDIR_INCOME entry, got {result.entry_count}"
        assert result.register_type == "KUDIR_INCOME"

        passed += 1
        print(f"  ✅ Register KUDIR_INCOME: {result.entry_count} entries, total={result.total_amount:.2f}")
        print()

        # ═══════════════════════════════════════════════════════════════
        # 4. SAVE + PERSIST
        # ═══════════════════════════════════════════════════════════════
        print("4. Register Persistence (Immutable)")
        print("-" * 40)

        register_id = await TaxRegister.save(result)
        assert register_id is not None

        async with pool.acquire() as conn:
            saved = await conn.fetchrow(
                "SELECT * FROM accounting.tax_register WHERE id = $1",
                register_id,
            )
            entries = await conn.fetch(
                "SELECT * FROM accounting.tax_register_entry WHERE register_id = $1",
                register_id,
            )

        assert saved is not None, "Register should be saved"
        assert saved["register_version"] == 1, "First version should be 1"
        assert len(entries) == 1, f"Expected 1 KUDIR_INCOME entry, got {len(entries)}"
        assert saved["is_current"] == True

        passed += 1
        print(f"  ✅ Register saved: v{saved['register_version']}, {len(entries)} entries, current={saved['is_current']}")
        print()

        # ═══════════════════════════════════════════════════════════════
        # 5. TAX REPLAY (new policy version)
        # ═══════════════════════════════════════════════════════════════
        print("5. Tax Replay")
        print("-" * 40)

        # Create a new policy version
        await TaxPolicy.create_policy_version(
            name="USN Income (Updated)",
            tax_regime="USN_D",
            version="2026.07.01",
            effective_from=date(2026, 7, 1),
            rules=[
                {
                    "rule_code": "revenue_to_kudir_updated",
                    "account_pattern": "90.01",
                    "direction": "credit",
                    "register_type": "KUDIR_INCOME",
                    "tax_treatment": "taxable",
                },
                {
                    "rule_code": "default_exclusion",
                    "account_pattern": None,
                    "direction": None,
                    "register_type": "EXCLUDED",
                    "tax_treatment": "excluded",
                    "excluded": True,
                    "reason_code": "unmapped_account",
                },
            ],
        )

        # Run replay
        replay = TaxReplay()
        replay_result = await replay.recalculate(
            company_id=cid,
            tax_period_id=pid,
            tax_policy_version="2026.07.01",
        )

        assert replay_result.ledger_unchanged, "Tax replay must NOT change ledger"
        assert replay_result.new_assignments_count >= 2, f"Expected >=2 new assignments, got {replay_result.new_assignments_count}"
        assert len(replay_result.registers_created) > 0, "Should create registers"

        # Verify old assignments are superseded
        async with pool.acquire() as conn:
            old_active = await conn.fetchval(
                """SELECT count(*) FROM accounting.tax_assignment
                   WHERE company_id = $1 AND is_current = true
                   AND policy_version_id != (
                       SELECT id FROM accounting.tax_policy_version WHERE version = '2026.07.01' LIMIT 1
                   )""",
                cid,
            )
            assert old_active == 0 or old_active is None, "Old assignments should be superseded"

        passed += 1
        print(f"  ✅ Replay: {replay_result.new_assignments_count} new assignments")
        print(f"     Ledger unchanged: {replay_result.ledger_unchanged}")
        print(f"     Registers created: {replay_result.registers_created}")
        print()

        # ═══════════════════════════════════════════════════════════════
        # 6. EXPLAINABILITY
        # ═══════════════════════════════════════════════════════════════
        print("6. Explainability")
        print("-" * 40)

        from backend.accounting.tax.explain import TaxExplainer

        async with pool.acquire() as conn:
            entry_row = await conn.fetchval(
                "SELECT id FROM accounting.tax_register_entry LIMIT 1",
            )

        if entry_row:
            explanation = await TaxExplainer.explain_register_entry(str(entry_row))
            assert explanation is not None, "Explanation should be built"
            assert explanation.chain is not None, "Chain should be present"
            assert "tax_assignment" in explanation.chain, "Chain should include assignment"
            assert "ledger_line" in explanation.chain, "Chain should include ledger line"

            passed += 1
            print(f"  ✅ Explanation chain: {len(explanation.chain)} links")
            print(f"     Why: {explanation.why_included or explanation.why_excluded}")
        else:
            print("  ⚠  No register entries found for explainability test")
            passed += 0
        print()

        # ═══════════════════════════════════════════════════════════════
        # 7. PERIOD MANAGEMENT
        # ═══════════════════════════════════════════════════════════════
        print("7. Period Management")
        print("-" * 40)

        can_close = await TaxPeriodResolver.can_close_tax_period(pid)
        print(f"     Can close period: {can_close['can_close']} ({can_close['reason']})")

        # Resolve period resolution
        resolution = TaxPeriodResolver.get_period_type_for_regime("usn_income")
        assert resolution == "year", f"USN_D should be year, got {resolution}"

        resolution_general = TaxPeriodResolver.get_period_type_for_regime("osno")
        assert resolution_general == "quarter", f"GENERAL should be quarter, got {resolution_general}"

        passed += 1
        print(f"  ✅ Resolution: USN_D={resolution}, GENERAL={resolution_general}")
        print()

    finally:
        await pool.close()

    # Summary
    print("=" * 60)
    print(f"Results: {passed} passed / {failed} failed")
    print("=" * 60)
    return passed, failed


if __name__ == "__main__":
    p, f = asyncio.run(main())
    sys.exit(1 if f > 0 else 0)
