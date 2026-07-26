#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$PWD"

echo "=== RealtorOS — restart ==="

# Build frontend
echo "[1] Building frontend..."
cd "$ROOT/frontend"
echo "  Cleaning Next.js cache..."
rm -rf "$ROOT/frontend/.next"
npx next build 2>&1 | tail -5

# Restart services via systemd
echo "[2] Restarting services..."
sudo systemctl restart realtoros-ocr-api 2>/dev/null || echo "  ⚠ OCR API systemd not found"
sleep 2
sudo systemctl restart realtoros-ocr-worker 2>/dev/null || echo "  ⚠ OCR Worker systemd not found"
sleep 1
sudo systemctl restart realtoros-api 2>/dev/null || echo "  ⚠ Backend systemd not found"
sudo systemctl restart realtoros-frontend 2>/dev/null || {
  echo "  ⚠ Frontend systemd restart failed — trying fallback..."
  # Kill any manually started Next.js process holding port 3000
  OLD_PID=$(lsof -ti :3000 2>/dev/null || true)
  if [ -n "$OLD_PID" ]; then
    echo "  Killing old process PID $OLD_PID on port 3000"
    kill "$OLD_PID" 2>/dev/null || true
    sleep 2
  fi
  sudo systemctl restart realtoros-frontend 2>/dev/null || echo "  ⚠ Frontend systemd restart failed again"
}

# Reload nginx to clear cached old HTML with stale chunk refs
echo "  Reloading nginx..."
sudo systemctl reload nginx 2>/dev/null || sudo systemctl restart nginx 2>/dev/null || echo "  ⚠ nginx reload/restart failed"

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
