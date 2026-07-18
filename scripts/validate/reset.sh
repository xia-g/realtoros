#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
echo "[reset] Dropping and recreating accounting schema..."
cd "$ROOT" && source venv/bin/activate
python -c "
import asyncio; from backend.accounting.db.pool import get_pool
async def reset():
    pool = await get_pool()
    async with pool.acquire() as conn:
        schemas = ['accounting']
        for s in schemas:
            tables = await conn.fetch(f"""SELECT tablename FROM pg_tables WHERE schemaname = '{s}'""")
            for t in tables:
                await conn.execute(f'DROP TABLE IF EXISTS {s}.{t["tablename"]} CASCADE')
        print('Cleaned schema')
    await pool.close()
asyncio.run(reset())
"
echo "[reset] Running migrations..."
python -m alembic upgrade head
echo "[reset] Reset complete"
