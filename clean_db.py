"""Clean database — keep only IP Shulgina (INN 780527855675)."""
import asyncio
import sys
sys.path.insert(0, 'backend')
from backend.accounting.db.pool import get_pool

async def clean():
    pool = await get_pool()
    async with pool.acquire() as conn:
        print("Deleting Test company...")
        await conn.execute("DELETE FROM public.companies WHERE inn = '7701123456'")

        print("Truncating accounting data...")
        for t in [
            'accounting_event', 'accounting_decision', 'ledger_line',
            'ledger_entry', 'posting_batch', 'posting_decision_link',
            'event_document', 'event_transaction', 'recognition_snapshot',
            'accounting_batch', 'decision_explanation',
            'tax_register', 'tax_register_line', 'tax_period_state',
            'report_draft', 'report_cell', 'report_template',
            'report_submission', 'report_audit_finding', 'report_audit_result',
            'reconciliation_run', 'reconciliation_item', 'reconciliation_match',
            'reconciliation_gap', 'reconciliation_explanation',
            'control_action', 'approval_workflow',
            'import_batch', 'import_record',
        ]:
            try:
                await conn.execute(f"TRUNCATE TABLE accounting.{t} CASCADE")
                print(f"  accounting.{t}: OK")
            except Exception as e:
                print(f"  accounting.{t}: {e}")

        print("Truncating seed data...")
        for t in ['documents', 'deals', 'properties', 'clients']:
            try:
                await conn.execute(f"TRUNCATE TABLE public.{t} CASCADE")
                print(f"  public.{t}: OK")
            except Exception as e:
                print(f"  public.{t}: {e}")

        # Verify
        companies = await conn.fetch("SELECT name, inn FROM public.companies")
        print(f"\nRemaining companies: {len(companies)}")
        for c in companies:
            print(f"  {c['name'][:40]} | INN: {c['inn']}")

    await pool.close()

asyncio.run(clean())
