# Runbook: Replay

**Когда:** Нужно пересчитать решение для одного или нескольких событий.

**Команда:**
```bash
# Одиночный replay
curl -X POST http://localhost:8090/api/v1/accounting/replay \
  -H 'Content-Type: application/json' \
  -d '{"event_id": "uuid", "ruleset_version": "2026.06.15"}'

# Массовый replay (через скрипт)
python -c "
import asyncio, asyncpg
async def run():
    conn = await asyncpg.connect('...')
    events = await conn.fetch(\"SELECT id FROM accounting.accounting_event WHERE ...\")
    for e in events:
        # call recalculate for each
        ...
asyncio.run(run())
"
```

**Проверка:** `GET /api/v1/accounting/events/{id}/decision`
