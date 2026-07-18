"""Integration test: real dataset import."""
import asyncio, csv, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__),"..",".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__),"..","..","backend"))
from backend.accounting.db.pool import get_pool
from backend.imports.bank import import_file

async def main():
    pool = await get_pool()
    dataset = os.path.abspath(os.path.join(os.path.dirname(__file__),"..","..","datasets","demo","bank_export.csv"))

    # Read CSV
    with open(dataset, "rb") as f:
        content = f.read()

    # Preview
    result = await import_file("bank_export.csv", content, "00000000-0000-0000-0000-000000000001")
    assert result.preview is not None, "Preview should return rows"
    assert result.duplicates < 5, f"Expected <5 duplicates, got {result.duplicates}"
    print(f"Preview: {len(result.preview)} rows, {len(result.warnings)} warnings")

    # Confirm
    confirmed = await import_file("bank_export.csv", content, "00000000-0000-0000-0000-000000000001", confirm=True)
    assert confirmed.events_created > 0, f"Expected events, got {confirmed.events_created}"
    assert confirmed.batch_id, "Should have batch_id"

    # Verify in DB
    async with pool.acquire() as conn:
        events = await conn.fetchval("SELECT count(*) FROM accounting.accounting_event WHERE source_system='bank_import'")
        print(f"Events in DB: {events}")

    print(f"\nBatch: {confirmed.batch_id}")
    print(f"Events: {confirmed.events_created}")
    print(f"Dups: {confirmed.duplicates}")
    print("PASS")

    await pool.close()
    return confirmed

if __name__ == "__main__":
    asyncio.run(main())
