"""Explainability Audit — verify full chain from any entity.

Check that each object answers:
  - why created
  - why included
  - why posted
  - why taxed
  - why reported
  - why reconciled
  - who approved

Coverage target: 100% chain from event → approval.
"""

import asyncio, sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "backend"))

from backend.accounting.db.pool import get_pool
from backend.accounting.tax.explain import TaxExplainer

chains = []

def check_chain(name, exists, detail=""):
    chains.append({"name": name, "exists": exists, "detail": detail})
    status = "✅" if exists else "❌"
    print(f"  {status} {name}" + (f" — {detail}" if detail else ""))


async def main():
    pool = await get_pool()
    print("=" * 60)
    print("Explainability Audit")
    print("=" * 60)

    async with pool.acquire() as conn:
        # 1. Event → why created
        event = await conn.fetchrow(
            "SELECT id, event_type, amount, source_type, created_at "
            "FROM accounting.accounting_event WHERE is_current = true LIMIT 1"
        )
        check_chain("Event → why created",
                    event is not None,
                    f"type={event['event_type']}" if event else "")

        # 2. Decision → why included/excluded
        dec = await conn.fetchrow(
            "SELECT id, included, reason FROM accounting.accounting_decision "
            "WHERE superseded_at IS NULL LIMIT 1"
        )
        check_chain("Decision → why included",
                    dec is not None and dec["reason"] is not None,
                    f"included={dec['included']} reason={dec['reason'][:50] if dec['reason'] else 'N/A'}" if dec else "")

        # 3. Decision → explanations
        expl = await conn.fetchval(
            "SELECT count(*) FROM accounting.decision_explanation LIMIT 1"
        )
        check_chain("Decision → explanations exist",
                    expl is not None and expl > 0,
                    f"{expl} explanations" if expl else "")

        # 4. Posting → why posted (posting_decision_link)
        pdl = await conn.fetchrow(
            "SELECT id, posting_rule_code, posting_rule_version "
            "FROM accounting.posting_decision_link LIMIT 1"
        )
        check_chain("Ledger → why posted",
                    pdl is not None,
                    f"rule={pdl['posting_rule_code']}" if pdl else "")

        # 5. Tax Assignment → why taxed
        ta = await conn.fetchrow(
            "SELECT id, register_type, tax_treatment, reason_code "
            "FROM accounting.tax_assignment WHERE is_current = true LIMIT 1"
        )
        check_chain("Tax Assignment → why taxed",
                    ta is not None and ta["reason_code"] is not None,
                    f"register={ta['register_type']} reason={ta['reason_code']}" if ta else "")

        # 6. Tax Explainability chain
        entry_row = await conn.fetchval(
            "SELECT id FROM accounting.tax_register_entry LIMIT 1"
        )
        if entry_row:
            explanation = await TaxExplainer.explain_register_entry(str(entry_row))
            check_chain("Tax Register Entry → explainable",
                        explanation is not None and explanation.chain is not None,
                        f"chain links={len(explanation.chain) if explanation and explanation.chain else 0}")
        else:
            check_chain("Tax Register Entry → explainable",
                        False, "no register entries exist — run E2E first")

        # 7. Report → why reported (cells + template)
        report = await conn.fetchrow(
            "SELECT id, status, report_hash, template_version_id FROM accounting.report_draft LIMIT 1"
        )
        check_chain("Report → why reported",
                    report is not None,
                    f"status={report['status']} hash={report['report_hash'][:12] if report else 'N/A'}" if report else "")

        # 8. Report cells have source_hash
        cell = await conn.fetchrow(
            "SELECT id, cell_code, source_hash FROM accounting.report_cell LIMIT 1"
        )
        check_chain("Report Cell → has source_hash",
                    cell is not None and cell["source_hash"] is not None,
                    f"cell={cell['cell_code']}" if cell else "")

        # 9. Audit findings → why warned
        af = await conn.fetchrow(
            "SELECT id, severity, category, description FROM accounting.report_audit_finding LIMIT 1"
        )
        check_chain("Audit Finding → why warned",
                    af is not None,
                    f"severity={af['severity']} desc={af['description'][:60] if af else 'N/A'}" if af else "")

        # 10. Reconciliation → why matched/unmatched
        rg = await conn.fetchrow(
            "SELECT id, severity, gap_type, description FROM accounting.reconciliation_gap LIMIT 1"
        )
        check_chain("Reconciliation Gap → explained",
                    rg is not None and rg["description"] is not None,
                    f"type={rg['gap_type']}" if rg else "")

        # 11. Control action → who approved
        ca = await conn.fetchrow(
            "SELECT id, action_type, actor_id, actor_role, status FROM accounting.control_action LIMIT 1"
        )
        check_chain("Control Action → who acted",
                    ca is not None,
                    f"actor={ca['actor_id'][:8] if ca and ca['actor_id'] else 'system'} role={ca['actor_role']}" if ca else "")

        # 12. Approval workflow → who approved
        aw = await conn.fetchrow(
            "SELECT id, status, approved_by, reason FROM accounting.approval_workflow LIMIT 1"
        )
        check_chain("Approval → who approved",
                    aw is not None,
                    f"status={aw['status']} by={aw['approved_by'][:8] if aw and aw['approved_by'] else 'pending'}" if aw else "")

    # Coverage
    print(f"\n{'='*60}")
    total = len(chains)
    covered = sum(1 for c in chains if c["exists"])
    print(f"Coverage: {covered}/{total} chains proven")
    print(f"{'='*60}")
    for c in chains:
        status = "✅" if c["exists"] else "❌"
        print(f"  {status} {c['name']}: {c['detail']}")

    # Broken chains
    broken = [c for c in chains if not c["exists"]]
    if broken:
        print(f"\n⚠  Broken chains ({len(broken)}):")
        for c in broken:
            print(f"  ❌ {c['name']} — missing")

    await pool.close()
    return covered, total - covered

if __name__ == "__main__":
    c, b = asyncio.run(main())
    sys.exit(1 if b > 0 else 0)
