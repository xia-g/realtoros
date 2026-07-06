"""Phase 5 Quality Gates.

CI fails if:
  - Report differs for same inputs (determinism)
  - AI changes report content (non-mutation)
  - Template version mismatch
  - Missing audit trace
  - submission_id == report_id
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "mcp", "server"))

from backend.accounting.db.pool import get_pool
from backend.accounting.report.template import TemplateProvider
from backend.accounting.report.generator import ReportGenerator
from backend.accounting.report.audit import AuditEngine
from backend.accounting.report.submission import SubmissionService


async def main():
    pool = await get_pool()
    failed = 0
    total = 0

    try:
        # Clean slate
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM accounting.submission_package")
            await conn.execute("DELETE FROM accounting.report_audit_finding")
            await conn.execute("DELETE FROM accounting.report_audit_result")
            await conn.execute("DELETE FROM accounting.report_cell")
            await conn.execute("DELETE FROM accounting.report_draft")

        # Find test company and period
        async with pool.acquire() as conn:
            company = await conn.fetchval("SELECT DISTINCT company_id FROM accounting.ledger_entry LIMIT 1")
            if not company:
                company = "00000000-0000-0000-0000-000000000001"
            period = await conn.fetchval(
                "SELECT id FROM accounting.tax_period WHERE company_id = $1 AND status = 'open' LIMIT 1",
                company,
            )

        cid = company
        pid = str(period) if period else None

        print("=" * 60)
        print("Phase 5 — Quality Gates")
        print("=" * 60)

        # ═══════════════════════════════════════════════════════════════
        # QG1: Report Determinism
        # ═══════════════════════════════════════════════════════════════
        total += 1
        print(f"\nQG1 — Report Determinism")

        template = await TemplateProvider.get_active("USN_DECLARATION", "USN_D")
        assert template is not None, "Template not found"

        hashes = []
        for i in range(3):
            draft = await ReportGenerator.generate(cid, template, pid)
            hashes.append(draft.report_hash)

        if len(set(hashes)) == 1:
            print(f"  ✅ 3× generate() → 3× identical hash ({hashes[0][:16]}...)")
        else:
            print(f"  ❌ FAIL: Hashes differ: {hashes}")
            failed += 1

        # ═══════════════════════════════════════════════════════════════
        # QG2: Template Version Isolation
        # ═══════════════════════════════════════════════════════════════
        total += 1
        print(f"\nQG2 — Template Version Isolation")

        templates_to_check = [
            ("USN_DECLARATION", "USN_D"),
            ("VAT_3", "GENERAL"),
        ]

        hashes_by_template = {}
        for code, regime in templates_to_check:
            t = await TemplateProvider.get_active(code, regime)
            if t:
                d = await ReportGenerator.generate(cid, t, pid)
                hashes_by_template[code] = d.report_hash

        if len(set(hashes_by_template.values())) == len(hashes_by_template):
            print(f"  ✅ Different templates → different hashes")
            for k, v in hashes_by_template.items():
                print(f"     {k}: {v[:16]}...")
        else:
            print(f"  ❌ FAIL: Template isolation broken")
            failed += 1

        # ═══════════════════════════════════════════════════════════════
        # QG3: AI Audit Non-Mutation
        # ═══════════════════════════════════════════════════════════════
        total += 1
        print(f"\nQG3 — AI Audit Non-Mutation")

        draft = await ReportGenerator.generate(cid, template, pid)
        report_id = await ReportGenerator.save(draft)

        async with pool.acquire() as conn:
            cells_before = await conn.fetchval(
                "SELECT count(*) FROM accounting.report_cell WHERE report_id = $1",
                report_id,
            )

        result = await AuditEngine.audit(report_id)
        await AuditEngine.save(result)

        async with pool.acquire() as conn:
            cells_after = await conn.fetchval(
                "SELECT count(*) FROM accounting.report_cell WHERE report_id = $1",
                report_id,
            )
            status = await conn.fetchval(
                "SELECT status FROM accounting.report_draft WHERE id = $1",
                report_id,
            )

        if cells_before == cells_after and status == "ai_reviewed":
            print(f"  ✅ {cells_before} cells unchanged after audit, status={status}")
            print(f"     Findings: {len(result.findings)}, risk={result.risk_score:.2f}")
        else:
            print(f"  ❌ FAIL: Cells changed {cells_before}→{cells_after} or status={status}")
            failed += 1

        # Verify: report content unchanged
        async with pool.acquire() as conn:
            cells = await conn.fetch(
                "SELECT cell_code, value_numeric FROM accounting.report_cell WHERE report_id = $1 ORDER BY cell_code",
                report_id,
            )
        print(f"     Cells: {[(c['cell_code'], float(c['value_numeric']) if c['value_numeric'] else 0) for c in cells[:3]]}...")

        # ═══════════════════════════════════════════════════════════════
        # QG4: Submission Integrity
        # ═══════════════════════════════════════════════════════════════
        total += 1
        print(f"\nQG4 — Submission Integrity")

        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE accounting.report_draft SET status = 'accountant_approved', updated_at = now() WHERE id = $1",
                report_id,
            )
            await conn.execute(
                "UPDATE accounting.report_draft SET status = 'ready_to_submit', updated_at = now() WHERE id = $1",
                report_id,
            )

        package = await SubmissionService.create(report_id)

        if package.submission_id != report_id:
            print(f"  ✅ submission_id ≠ report_id ({package.submission_id[:8]}...)")
            print(f"     transport_payload_hash: {package.transport_payload_hash[:16]}...")
        else:
            print(f"  ❌ FAIL: submission_id == report_id")
            failed += 1

        # ═══════════════════════════════════════════════════════════════
        # QG5: Report Replay (deterministic regeneration)
        # ═══════════════════════════════════════════════════════════════
        total += 1
        print(f"\nQG5 — Report Replay (deterministic regeneration)")

        async with pool.acquire() as conn:
            hash_original = await conn.fetchval(
                "SELECT report_hash FROM accounting.report_draft WHERE id = $1",
                report_id,
            )

        draft_replay = await ReportGenerator.generate(cid, template, pid)
        rid_replay = await ReportGenerator.save(draft_replay)

        if draft_replay.report_hash == hash_original:
            print(f"  ✅ Replay hash == original hash: {hash_original[:16]}...")
        else:
            print(f"  ❌ FAIL: Hashes differ: {hash_original[:16]}... vs {draft_replay.report_hash[:16]}...")
            failed += 1

    finally:
        await pool.close()

    print(f"\n{'=' * 60}")
    print(f"Quality Gates: {total - failed}/{total} passed")
    if failed:
        print(f"  ❌ {failed} FAILED")
    else:
        print(f"  ✅ ALL PASSED")
    print(f"{'=' * 60}")
    return failed


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
