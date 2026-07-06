#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
echo "========================================"
echo "Validation Track — Run All"
echo "========================================"
echo ""
echo "==> Stage 1: Environment"
bash "$ROOT/scripts/validate/bootstrap.sh"
echo ""
echo "==> Stage 2: Smoke Tests"
cd "$ROOT" && source venv/bin/activate && python -m pytest tests/validation/smoke/ -v --tb=short 2>&1 | tail -30 || true
echo ""
echo "==> Stage 3: Full E2E"
cd "$ROOT" && source venv/bin/activate && python -m pytest tests/validation/e2e/ -v --tb=short 2>&1 | tail -30 || true
echo ""
echo "==> Stage 4: Failure Injection"
cd "$ROOT" && source venv/bin/activate && python -m pytest tests/validation/failure/ -v --tb=short 2>&1 | tail -30 || true
echo ""
echo "==> Stage 5: Explainability"
cd "$ROOT" && source venv/bin/activate && python -m pytest tests/validation/explainability/ -v --tb=short 2>&1 | tail -30 || true
echo ""
echo "==> Stage 6: Performance"
cd "$ROOT" && source venv/bin/activate && python tests/validation/perf/load_test.py 2>&1 | tail -20 || true
echo ""
echo "========================================"
echo "Validation Track Complete"
echo "========================================"
