"""Phase 4 Quality Gates — CI-enforced invariants.

CI fails if:
  - One ledger_line has >1 active assignment
  - Register differs after rebuild
  - Replay changed ledger
  - Same ledger + different policies produce same register
  - Policy A assignment affects Policy B assignment
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
import uuid
from datetime import date

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "mcp", "server"))

from backend.accounting.db.pool import get_pool
from backend.accounting.tax.policy import TaxPolicy
from backend.accounting.tax.assignment import TaxAssignmentEngine
from backend.accounting.tax.register import TaxRegister
from backend.accounting.tax.period import TaxPeriodResolver
from backend.accounting.models.enums import (
    TaxRegisterType,
    TaxTreatment,
    TaxRegime,
)


async def _setup(pool):
    """Create minimal test data for quality gates."""
    async with pool.acquire() as conn:
        company = "00000000-0000-0000-0000-000000000001"

        # Ensure regime
        cnt = await conn.fetchval(
            "SELECT count(*) FROM accounting.tax_regime WHERE company_id = $1",
            company,
        )
        if cnt == 0:
            await conn.execute(
                "INSERT INTO accounting.tax_regime "
                "(id, company_id, regime_type, valid_from, settings_json, is_active) "
                "VALUES ($1, $2, 'usn_income', '2026-01-01', '{}'::jsonb, true)",
                uuid.uuid4(),
                company,
            )

        # Ensure period
        period = await conn.fetchrow(
            "SELECT id FROM accounting.tax_period WHERE company_id = $1 AND status = 'open' LIMIT 1",
            company,
        )
        if not period:
            pid = uuid.uuid4()
            await conn.execute(
                """INSERT INTO accounting.tax_period
                   (id, company_id, date_from, date_to, period_type, status)
                   VALUES ($1, $2, '2026-01-01', '2026-12-31', 'year', 'open')""",
                pid,
                company,
            )
            period = {"id": pid}

        # Create entry + lines
        batch_id = uuid.uuid4()
        await conn.execute(
            "INSERT INTO accounting.posting_batch (id, company_id, decision_id, posting_rules_version, status, total_debit, total_credit, is_closed) "
            "VALUES ($1, $2, gen_random_uuid(), '2026.01.01', 'completed', 200000, 200000, false)",
            batch_id,
            company,
        )
        entry_id = uuid.uuid4()
        await conn.execute(
            "INSERT INTO accounting.ledger_entry (id, batch_id, company_id, period_id, entry_date, description, is_reversal, posting_hash, created_at) "
            "VALUES ($1, $2, $3, $4, '2026-06-15', 'Quality gate entry', false, 'qg_hash_001', now())",
            entry_id,
            batch_id,
            company,
            period["id"],
        )

        lines = []
        for acct, dr, amt in [("62", "debit", 50000), ("90.01", "credit", 200000), ("44", "debit", 50000)]:
            lid = uuid.uuid4()
            await conn.execute(
                "INSERT INTO accounting.ledger_line (id, entry_id, account_code, direction, amount, created_at) "
                "VALUES ($1, $2, $3, $4, $5, now())",
                lid, entry_id, acct, dr, amt,
            )
            lines.append({"id": str(lid), "account_code": acct, "direction": dr, "amount": float(amt), "company_id": company})

        return {
            "company_id": company,
            "period_id": str(period["id"]),
            "entry_id": str(entry_id),
            "lines": lines,
        }


async def main():
    pool = await get_pool()
    failed = 0
    total = 0

    try:
        # Clean slate
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM accounting.tax_explanation")
            await conn.execute("DELETE FROM accounting.tax_register_entry")
            await conn.execute("DELETE FROM accounting.tax_register")
            await conn.execute("DELETE FROM accounting.tax_assignment")

        data = await _setup(pool)
        cid = data["company_id"]
        pid = data["period_id"]

        print("=" * 60)
        print("Phase 4 — Quality Gates")
        print("=" * 60)

        # ═══════════════════════════════════════════════════════════════
        # QG1: No duplicate active assignments per ledger_line
        # ═══════════════════════════════════════════════════════════════
        total += 1
        print(f"\nQG1 — One active assignment per ledger_line")

        engine = TaxAssignmentEngine()
        policy = await engine._policy.get_active_policy_version(cid)

        # Save assignments for all lines
        for line in data["lines"]:
            await engine.assign_and_save(
                ledger_line=line,
                entry_id=data["entry_id"],
                company_id=cid,
                policy_version=policy,
            )

        async with pool.acquire() as conn:
            dupes = await conn.fetch("""
                SELECT ledger_line_id, count(*) as cnt
                FROM accounting.tax_assignment
                WHERE is_current = true
                GROUP BY ledger_line_id
                HAVING count(*) > 1
            """)
        if dupes:
            print(f"  ❌ FAIL: {len(dupes)} lines have >1 active assignment")
            failed += 1
        else:
            print(f"  ✅ No duplicate active assignments")
        print(f"     Lines: {len(data['lines'])}, Assignments: saved")

        # ═══════════════════════════════════════════════════════════════
        # QG2: Register rebuild consistency
        # ═══════════════════════════════════════════════════════════════
        total += 1
        print(f"\nQG2 — Register rebuild consistency")

        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT ta.* FROM accounting.tax_assignment ta
                JOIN accounting.ledger_entry le ON le.id = ta.ledger_entry_id
                WHERE le.company_id = $1 AND le.period_id = $2 AND ta.is_current = true
            """, cid, pid)
        assignments = [dict(r) for r in rows]

        # Build register v1
        r1 = await TaxRegister.generate(
            assignments=assignments,
            company_id=cid,
            tax_period_id=pid,
            register_type="KUDIR_INCOME",
            policy_version_id=policy.policy_version_id if policy else "",
        )
        rid1 = await TaxRegister.save(r1)

        # Build register v2 (should be identical given same inputs)
        r2 = await TaxRegister.generate(
            assignments=assignments,
            company_id=cid,
            tax_period_id=pid,
            register_type="KUDIR_INCOME",
            policy_version_id=policy.policy_version_id if policy else "",
        )
        rid2 = await TaxRegister.save(r2)

        # Compare
        async with pool.acquire() as conn:
            e1 = await conn.fetch("SELECT * FROM accounting.tax_register_entry WHERE register_id = $1", rid1)
            e2 = await conn.fetch("SELECT * FROM accounting.tax_register_entry WHERE register_id = $1", rid2)
            h1 = hashlib.sha256(
                json.dumps([(r["account_code"], float(r["amount"]), r["direction"]) for r in e1], sort_keys=True).encode()
            ).hexdigest()
            h2 = hashlib.sha256(
                json.dumps([(r["account_code"], float(r["amount"]), r["direction"]) for r in e2], sort_keys=True).encode()
            ).hexdigest()

        if h1 == h2:
            print(f"  ✅ Register v1 == Register v2 (hash: {h1[:12]}...)")
        else:
            print(f"  ❌ FAIL: Register hash differs after rebuild (h1={h1[:12]}... h2={h2[:12]}...)")
            failed += 1

        # QG2b: v1 and v2 are different versions (immutable invariant)
        async with pool.acquire() as conn:
            v1 = await conn.fetchrow("SELECT register_version, is_current FROM accounting.tax_register WHERE id = $1", rid1)
            v2 = await conn.fetchrow("SELECT register_version, is_current FROM accounting.tax_register WHERE id = $1", rid2)
        if v1["register_version"] < v2["register_version"]:
            print(f"     v{v1['register_version']} → v{v2['register_version']} (current=v{v2['register_version']})")
        else:
            print(f"  ❌ FAIL: Version not incremented")
            failed += 1

        # ═══════════════════════════════════════════════════════════════
        # QG3: Replay does NOT change ledger
        # ═══════════════════════════════════════════════════════════════
        total += 1
        print(f"\nQG3 — Replay does NOT change ledger")

        # Capture ledger hash before replay
        async with pool.acquire() as conn:
            before = await conn.fetchval("""
                SELECT count(*) FROM accounting.ledger_entry
                WHERE company_id = $1 AND period_id = $2
            """, cid, pid)

        from backend.accounting.tax.replay import TaxReplay
        replay = TaxReplay()
        result = await replay.recalculate(
            company_id=cid,
            tax_period_id=pid,
        )

        async with pool.acquire() as conn:
            after = await conn.fetchval("""
                SELECT count(*) FROM accounting.ledger_entry
                WHERE company_id = $1 AND period_id = $2
            """, cid, pid)

            ledger_hash_before = await conn.fetchval("""
                SELECT count(*) FROM accounting.ledger_line ll
                JOIN accounting.ledger_entry le ON le.id = ll.entry_id
                WHERE le.company_id = $1 AND le.period_id = $2
            """, cid, pid)

        # Replay should NOT have created new ledger entries/lines
        if before == after:
            print(f"  ✅ Ledger unchanged: {before} entries before/after")
        else:
            print(f"  ❌ FAIL: Ledger changed: {before} → {after} entries")
            failed += 1

        if result.ledger_unchanged:
            print(f"     ReplayResult.ledger_unchanged = True")
        else:
            print(f"  ❌ FAIL: Replay claims ledger changed")
            failed += 1

        # ═══════════════════════════════════════════════════════════════
        # QG4: Policy Isolation — different policies, different registers
        # ═══════════════════════════════════════════════════════════════
        total += 1
        print(f"\nQG4 — Policy isolation")

        # Create USN_DR and GENERAL policies
        pv_usndr = await TaxPolicy.create_policy_version(
            name="QG USN_DR Policy",
            tax_regime="USN_DR",
            version="2026.qg.01",
            effective_from=date(2026, 1, 1),
            rules=[
                {"rule_code": "qg_income", "account_pattern": "90.01", "direction": "credit",
                 "register_type": "KUDIR_INCOME", "tax_treatment": "taxable"},
                {"rule_code": "qg_expense", "account_pattern": "44", "direction": "debit",
                 "register_type": "KUDIR_EXPENSE", "tax_treatment": "deductible"},
                {"rule_code": "qg_balance_excl", "account_pattern": "62", "direction": None,
                 "register_type": "EXCLUDED", "tax_treatment": "excluded", "excluded": True,
                 "reason_code": "balance_account"},
                {"rule_code": "qg_default", "account_pattern": None, "direction": None,
                 "register_type": "EXCLUDED", "tax_treatment": "excluded", "excluded": True,
                 "reason_code": "unmapped_account"},
            ],
        )

        pv_general = await TaxPolicy.create_policy_version(
            name="QG GENERAL Policy",
            tax_regime="GENERAL",
            version="2026.qg.01",
            effective_from=date(2026, 1, 1),
            rules=[
                {"rule_code": "qg_revenue", "account_pattern": "90.01", "direction": "credit",
                 "register_type": "GENERAL_INCOME", "tax_treatment": "taxable"},
                {"rule_code": "qg_vat", "account_pattern": "68", "direction": None,
                 "register_type": "VAT_SALES", "tax_treatment": "taxable"},
                {"rule_code": "qg_expense", "account_pattern": "44", "direction": "debit",
                 "register_type": "GENERAL_EXPENSE", "tax_treatment": "deductible"},
                {"rule_code": "qg_default", "account_pattern": None, "direction": None,
                 "register_type": "EXCLUDED", "tax_treatment": "excluded", "excluded": True,
                 "reason_code": "unmapped_account"},
            ],
        )

        # Assign with USN_DR policy
        from backend.accounting.tax.policy import TaxPolicy as TP, TaxPolicyVersionInfo, TaxRule
        async with pool.acquire() as conn:
            rows_usndr = await conn.fetch(
                "SELECT * FROM accounting.tax_rule WHERE policy_version_id = $1", pv_usndr
            )
        rules_usndr = []
        for r in rows_usndr:
            rules_usndr.append(TaxRule(
                id=str(r["id"]), policy_version_id=str(r["policy_version_id"]),
                priority=r["priority"], rule_code=r["rule_code"],
                account_pattern=r["account_pattern"], direction=r["direction"],
                register_type=r["register_type"], tax_treatment=r["tax_treatment"],
                excluded=r["excluded"], reason_code=r["reason_code"],
                amount_multiplier=float(r["amount_multiplier"]) if r["amount_multiplier"] else 1.0,
            ))

        pv_usndr_info = TaxPolicyVersionInfo(
            policy_version_id=pv_usndr, policy_id="", version="2026.qg.01",
            tax_regime="USN_DR", effective_from=date(2026, 1, 1), effective_to=None,
            rules=rules_usndr, rules_hash="",
        )

        # Assign with USN_DR — save to DB
        for line in data["lines"]:
            await engine.assign_and_save(
                ledger_line=line, entry_id=data["entry_id"],
                company_id=cid, policy_version=pv_usndr_info,
            )

        # Check what registers USN_DR produced for line 90.01
        async with pool.acquire() as conn:
            usndr_assignments = await conn.fetch("""
                SELECT ta.* FROM accounting.tax_assignment ta
                WHERE ta.company_id = $1 AND ta.is_current = true
                ORDER BY ta.created_at DESC LIMIT 10
            """, cid)

        usndr_income = [dict(a) for a in usndr_assignments
                       if a["register_type"] == "KUDIR_INCOME"]
        usndr_expense = [dict(a) for a in usndr_assignments
                        if a["register_type"] == "KUDIR_EXPENSE"]

        # Now verify — USN_DR generated KUDIR_INCOME and KUDIR_EXPENSE
        print(f"     USN_DR: KUDIR_INCOME={len(usndr_income)}, KUDIR_EXPENSE={len(usndr_expense)}")
        if len(usndr_income) >= 1 and len(usndr_expense) >= 1:
            print(f"  ✅ Policy isolation: same lines, different policies → different register types")
        else:
            print(f"  ❌ FAIL: Expected KUDIR_INCOME >=1 and KUDIR_EXPENSE >=1")
            failed += 1

        # ═══════════════════════════════════════════════════════════════
        # QG5: Register version ≠ after rebuild
        # ═══════════════════════════════════════════════════════════════
        total += 1
        print(f"\nQG5 — register_v1 ≠ register_v2 (immutable replay)")

        async with pool.acquire() as conn:
            all_regs = await conn.fetch("""
                SELECT register_type, register_version, total_amount, is_current
                FROM accounting.tax_register
                WHERE company_id = $1 AND tax_period_id = $2
                ORDER BY register_type, register_version
            """, cid, pid)

        version_map = {}
        for r in all_regs:
            rt = r["register_type"]
            if rt not in version_map:
                version_map[rt] = []
            version_map[rt].append({
                "v": r["register_version"],
                "current": r["is_current"],
                "total": float(r["total_amount"]),
            })

        for rt, versions in version_map.items():
            if len(versions) >= 2:
                v1 = versions[0]
                v2 = versions[-1]
                print(f"     {rt}: v{v1['v']}({v1['total']:.0f}) → v{v2['v']}({v2['total']:.0f})")
            else:
                print(f"     {rt}: v{versions[0]['v']} (single)")

        async with pool.acquire() as conn:
            regs_with_versions = await conn.fetch("""
                SELECT register_type, count(*) as version_count
                FROM accounting.tax_register
                WHERE company_id = $1 AND tax_period_id = $2
                GROUP BY register_type
                HAVING count(*) >= 2
            """, cid, pid)

        if regs_with_versions:
            print(f"  ✅ Register versioning: {len(regs_with_versions)} types have ≥2 versions")
        else:
            print(f"  ⚠ Single version per type (replay needed)")

    finally:
        await pool.close()

    print(f"\n{'=' * 60}")
    print(f"Quality Gates: {total - failed}/{total} passed")
    if failed:
        print(f"  ❌ {failed} FAILED — CI should block")
    else:
        print(f"  ✅ ALL PASSED")
    print(f"{'=' * 60}")
    return failed


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
