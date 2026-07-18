#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$PWD"

echo "=== RealtorOS — restart ==="

# Build frontend
echo "[1] Building frontend..."
cd "$ROOT/frontend"
npx next build 2>&1 | tail -5

# Restart services via systemd
echo "[2] Restarting services..."
sudo systemctl restart realtoros-ocr-api 2>/dev/null || echo "  ⚠ OCR API systemd not found"
sleep 2
sudo systemctl restart realtoros-ocr-worker 2>/dev/null || echo "  ⚠ OCR Worker systemd not found"
sleep 1
sudo systemctl restart realtoros-api 2>/dev/null || echo "  ⚠ Backend systemd not found"
sudo systemctl restart realtoros-frontend 2>/dev/null || echo "  ⚠ Frontend systemd not found"

# Wait for services
sleep 6

# Health checks
echo ""
echo "[3] Health checks..."
curl -sf http://127.0.0.1:8090/health > /dev/null && echo "  ✅ Backend  :8090 — OK" || echo "  ❌ Backend  :8090 — FAIL"
curl -sfI http://127.0.0.1:3000/ > /dev/null && echo "  ✅ Frontend :3000 — OK" || echo "  ❌ Frontend :3000 — FAIL"
curl -sf http://127.0.0.1:8001/api/v1/health > /dev/null && echo "  ✅ OCR API  :8001 — OK" || echo "  ❌ OCR API  :8001 — FAIL"

echo ""
echo "=== Done ==="
echo "Backend:  http://127.0.0.1:8090"
echo "Frontend: http://127.0.0.1:3000"
echo "OCR:      http://127.0.0.1:8001"
