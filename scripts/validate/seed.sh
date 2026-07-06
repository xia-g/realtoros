#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT" && source venv/bin/activate
echo "[seed] Seeding default tax policies..."
python -c "
import asyncio; import sys; sys.path.insert(0, 'backend')
from backend.accounting.tax.policy import TaxPolicy; asyncio.run(TaxPolicy.seed_default_policies())
print('Tax policies seeded')
"
echo "[seed] Seeding report templates..."
python -c "
import asyncio; import sys; sys.path.insert(0, 'backend')
from backend.accounting.report.template import TemplateProvider; asyncio.run(TemplateProvider.seed_default_templates())
print('Report templates seeded')
"
echo "[seed] Creating validation dataset..."
python -c "
import asyncio; import sys; sys.path.insert(0, 'backend')
from backend.accounting.db.pool import get_pool
from datetime import date
async def seed():
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Ensure company + regime + period
        company = '00000000-0000-0000-0000-000000000001'
        reg = await conn.fetchval('SELECT count(*) FROM accounting.tax_regime WHERE company_id=\$1', company)
        if reg == 0:
            await conn.execute('INSERT INTO accounting.tax_regime (id,company_id,regime_type,valid_from,settings_json,is_active) VALUES (gen_random_uuid(),\$1,\'usn_income\',\'2026-01-01\',\'{}\'::jsonb,true)', company)
        per = await conn.fetchval('SELECT count(*) FROM accounting.tax_period WHERE company_id=\$1 AND status=\'open\'', company)
        if per == 0:
            await conn.execute('INSERT INTO accounting.tax_period (id,company_id,date_from,date_to,period_type,status) VALUES (gen_random_uuid(),\$1,\'2026-01-01\',\'2026-12-31\',\'year\',\'open\')', company)
        print(f'Validation dataset ready for company {company}')
    await pool.close()
asyncio.run(seed())
"
echo "[seed] Done"
