#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
echo "[bootstrap] Setting up validation environment..."
# Start PostgreSQL if not running
if ! pg_isready -q 2>/dev/null; then
  echo "[bootstrap] Starting PostgreSQL..."
  sudo service postgresql start 2>/dev/null || pg_ctlcluster 16 main start 2>/dev/null || true
  sleep 2
fi
# Apply migrations
echo "[bootstrap] Applying Alembic migrations..."
cd "$ROOT" && source venv/bin/activate && python -m alembic upgrade head
echo "[bootstrap] Seeding tax policies..."
cd "$ROOT" && source venv/bin/activate && python -c "
import asyncio; import sys; sys.path.insert(0, 'backend')
from backend.accounting.tax.policy import TaxPolicy; asyncio.run(TaxPolicy.seed_default_policies())
from backend.accounting.report.template import TemplateProvider; asyncio.run(TemplateProvider.seed_default_templates())
print('Seeded: tax policies + report templates')
"
echo "[bootstrap] Starting backend (uvicorn)..."
cd "$ROOT" && source venv/bin/activate
uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
echo "[bootstrap] Backend PID=$BACKEND_PID"
# Wait for backend
for i in $(seq 1 30); do
  if curl -s http://localhost:8000/health >/dev/null 2>&1; then
    echo "[bootstrap] Backend ready"
    break
  fi
  sleep 1
done
echo "[bootstrap] Starting frontend (next dev)..."
cd "$ROOT/frontend" && npx next dev -p 3000 &
FRONTEND_PID=$!
echo "[bootstrap] Frontend PID=$FRONTEND_PID"
echo "[bootstrap] Environment ready: backend=:8000 frontend=:3000"
echo "BACKEND_PID=$BACKEND_PID" > /tmp/validate.pids
echo "FRONTEND_PID=$FRONTEND_PID" >> /tmp/validate.pids
