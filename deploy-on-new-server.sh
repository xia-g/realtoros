#!/usr/bin/env bash
# Запускать НА НОВОМ сервере 192.168.1.109
set -euo pipefail

cd /home/xiag/real-estate-os

echo "=== Setting up RealtorOS on new server ==="

# PostgreSQL restore
echo "[1] Restoring PostgreSQL..."
sudo -u postgres psql -c "CREATE USER realtoros WITH PASSWORD 'realtoros15!';" 2>/dev/null || true
sudo -u postgres psql -c "CREATE DATABASE realtoros OWNER realtoros;" 2>/dev/null || true
sudo -u postgres psql -c "ALTER USER realtoros CREATEDB;" 2>/dev/null || true
pg_restore -U realtoros -h 127.0.0.1 -d realtoros --no-owner --no-acl /home/xiag/real-estate-os/realtoros.dump
echo "  Done."

# MySQL restore (optional)
if [ -f /home/xiag/real-estate-os/ttbot.sql ]; then
  echo "[2] Restoring MySQL..."
  sudo mysql -e "CREATE DATABASE IF NOT EXISTS bot;" 2>/dev/null || true
  sudo mysql bot < /home/xiag/real-estate-os/ttbot.sql 2>/dev/null || echo "  Skipped (MySQL not ready)"
fi

# Python venv
echo "[3] Creating Python venv..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel -q
pip install fastapi uvicorn sqlalchemy asyncpg httpx pydantic \
  python-dotenv pydantic-settings python-multipart structlog \
  pyjwt passlib pytest pytest-asyncio -q
echo "  Done."

# Frontend
echo "[4] Building frontend..."
cd /home/xiag/real-estate-os/frontend
npm ci --omit=dev 2>/dev/null || npm install
npx next build
echo "  Done."

# MCP Server
echo "[5] Setting up MCP server..."
cd /var/www/mcp-server
npm ci --omit=dev 2>/dev/null || npm install
echo "  Done."

# Systemd service
echo "[6] Installing systemd service..."
sudo tee /etc/systemd/system/realtoros-api.service > /dev/null << 'SERVICEEOF'
[Unit]
Description=Real Estate OS — Backend API
After=network.target postgresql.service

[Service]
Type=simple
User=xiag
Group=prmer
WorkingDirectory=/home/xiag/real-estate-os
Environment=PYTHONPATH=/home/xiag/real-estate-os
ExecStart=/home/xiag/real-estate-os/venv/bin/uvicorn backend.main:app \
  --host 0.0.0.0 --port 8090 --workers 1 --log-level info
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICEEOF

sudo systemctl daemon-reload
sudo systemctl enable --now realtoros-api
echo "  Done."

# Nginx configs
echo "[7] Installing nginx configs..."
sudo cp /home/xiag/real-estate-os/nginx-sites/* /etc/nginx/sites-enabled/ 2>/dev/null || true
sudo nginx -t && sudo systemctl reload nginx || echo "  Check nginx configs manually"
echo "  Done."

# Frontend autostart
echo "[8] Starting frontend..."
cd /home/xiag/real-estate-os/frontend
nohup npx next start --port 3000 > /tmp/next.log 2>&1 &
echo "  Started (PID: $!)"

echo ""
echo "=== Migration complete! ==="
echo "Check: curl http://127.0.0.1:8090/health"
echo "       curl http://127.0.0.1:3000"
