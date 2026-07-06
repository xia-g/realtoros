# Quick Start — 5 минут до первого отчёта

## 1. Запуск

```bash
cd /home/xiag/real-estate-os

# Активировать окружение
source venv/bin/activate

# Проверить миграции (если не применялись)
python -m alembic upgrade head

# Запустить backend
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload &
# Ждём готовности:
sleep 3 && curl -s http://localhost:8000/api/v1/accounting/events?limit=1 | head -c 100

# Запустить frontend (в отдельном терминале или фоном)
cd frontend && npx next dev -p 3000 &
```

**Проверка:** открыть `http://localhost:3000` — должен загрузиться Dashboard.

---

## 2. Первичные данные

```bash
# Засеять налоговые политики (3 шт) + шаблоны отчётов (3 шт)
cd /home/xiag/real-estate-os && source venv/bin/activate

python -c "
import asyncio
import sys; sys.path.insert(0, 'backend')
from backend.accounting.tax.policy import TaxPolicy
from backend.accounting.report.template import TemplateProvider
asyncio.run(TaxPolicy.seed_default_policies())
asyncio.run(TemplateProvider.seed_default_templates())
print('Seeded: tax policies + report templates')
"
```

Или через API:

```bash
curl -X POST http://localhost:8000/api/v1/tax/seed
curl -X POST http://localhost:8000/api/v1/reports/templates/seed
```

---

## 3. Импорт банковской выписки

```bash
# Сгенерировать демо-датасет (1000 строк)
python backend/imports/datasets/demo/generate.py

# Импортировать в систему (preview без подтверждения)
python -c "
import asyncio
import sys; sys.path.insert(0, 'backend')
from backend.imports.bank import import_file

async def run():
    with open('datasets/demo/bank_export.csv', 'rb') as f:
        content = f.read()
    result = await import_file('bank_export.csv', content, '00000000-0000-0000-0000-000000000001', confirm=True)
    print(f'Batch: {result.batch_id}')
    print(f'Events: {result.events_created}')
    print(f'Duplicates: {result.duplicates}')
    print(f'Warnings: {result.warnings}')

asyncio.run(run())
"
```

Или через WebUI: `http://localhost:3000/imports`

---

## 4. Полный pipeline (10 шагов)

```bash
python tests/validation/e2e/test_full_flow.py
```

Результат за ~20 секунд:

```
 1 Import → Decision        110ms ✅
 2 Post → Ledger            175ms ✅
 3 Tax Assignment            78ms ✅
 4 Register                 104ms ✅
 5 Report                   103ms ✅
 6 AI Audit                 152ms ✅
 7 Submission                61ms ✅
 8 Reconciliation          18865ms ✅
 9 Approval                 213ms ✅
10 Close Period              17ms ✅
```

---

## 5. WebUI — страницы

| URL | Что |
|-----|-----|
| `http://localhost:3000/` | Dashboard |
| `http://localhost:3000/accounting/events` | Event Explorer |
| `http://localhost:3000/accounting/decisions` | Decision Explorer |
| `http://localhost:3000/accounting/replay` | Replay Console |
| `http://localhost:3000/ledger/entries` | Ledger Explorer |
| `http://localhost:3000/ledger/accounts` | Chart of Accounts |
| `http://localhost:3000/ledger/periods` | Period Management |
| `http://localhost:3000/tax/registers` | Tax Registers |
| `http://localhost:3000/tax/assignments` | Tax Assignments |
| `http://localhost:3000/tax/policies` | Tax Policies |
| `http://localhost:3000/reports/drafts` | Report Drafts |
| `http://localhost:3000/reports/templates` | Report Templates |
| `http://localhost:3000/reports/audit` | Report Audit |
| `http://localhost:3000/reconciliation/runs` | Reconciliation Runs |
| `http://localhost:3000/reconciliation/matches` | Reconciliation Matches |
| `http://localhost:3000/reconciliation/gaps` | Reconciliation Gaps |
| `http://localhost:3000/control/actions` | Control Actions (audit log) |
| `http://localhost:3000/control/approval` | Approval Queue |
| `http://localhost:3000/control/state` | System State |
| `http://localhost:3000/control/metrics` | Metrics |
| `http://localhost:3000/imports` | Bank Import |
| `http://localhost:3000/imports/documents` | Document Intake |
| `http://localhost:3000/imports/ocr` | OCR Classification |
| `http://localhost:3000/imports/history` | Import History |

---

## 6. API — быстрые проверки

```bash
# Health
curl -s http://localhost:8000/health | python3 -m json.tool

# Статус системы
curl -s http://localhost:8000/api/v1/control/state | python3 -m json.tool

# Количество событий
curl -s http://localhost:8000/api/v1/accounting/events?limit=1 | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Events: {d[\"total\"]}')"

# Tax policies
curl -s http://localhost:8000/api/v1/tax/policies | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Policies: {len(d[\"items\"])}')"

# Report templates
curl -s http://localhost:8000/api/v1/reports/templates | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Templates: {len(d[\"items\"])}')"

# Reconciliation runs
curl -s http://localhost:8000/api/v1/reconciliation/runs?limit=5 | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Recon runs: {d[\"total\"]}')"

# Metrics
curl -s http://localhost:8000/api/v1/control/metrics?limit=1 | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d['items'][0],indent=2) if d['items'] else 'No metrics')"
```

---

## 7. Остановка

```bash
kill $(cat /tmp/validate.pids 2>/dev/null) 2>/dev/null || true
# Или вручную: kill <PID uvicorn> <PID next>
```

---

## 8. Если что-то пошло не так

```bash
# Сброс всей accounting схемы (данные потеряются!)
bash scripts/validate/reset.sh

# Заново: миграции
python -m alembic upgrade head

# Заново: seed
bash scripts/validate/seed.sh
```
