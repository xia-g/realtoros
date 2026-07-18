#!/usr/bin/env bash
# Migration script: текущий сервер → 192.168.1.109
# Запускать НА СТАРОМ сервере.
set -euo pipefail

NEW_SERVER="${1:-xiag@192.168.1.109}"
SSH_PORT="${2:-222}"
NEW_IP="192.168.1.109"
SSH_CMD="ssh -p ${SSH_PORT}"
SCP_CMD="scp -P ${SSH_PORT}"

echo "=== RealtorOS Migration to ${NEW_IP} (port ${SSH_PORT}) ==="
echo ""

# ── 1. Дамп PostgreSQL ──
echo "[1/4] Dumping PostgreSQL..."
pg_dump -U realtoros -h 127.0.0.1 -d realtoros --no-owner --no-acl \
  -F c -f /home/xiag/real-estate-os/realtoros.dump
echo "  Done: /home/xiag/real-estate-os/realtoros.dump"

# ── 2. Дамп MySQL (опционально) ──
echo "[2/4] Dumping MySQL (ttbot)..."
mysqldump -u bot -pBot_Pass15 -h 127.0.0.1 bot > /home/xiag/real-estate-os/ttbot.sql 2>/dev/null && \
  echo "  Done: /home/xiag/real-estate-os/ttbot.sql" || echo "  Skipped (MySQL not available)"

# ── 3. Ensure all files are readable ──
echo "[5/5] Fixing file permissions for transfer..."
find /home/xiag/real-estate-os -type f ! -perm -o=r ! -path '*/node_modules/*' ! -path '*/.git/*' -exec chmod o+r {} \; 2>/dev/null || true
find /var/www/mcp-server -type f ! -perm -o=r ! -path '*/node_modules/*' -exec chmod o+r {} \; 2>/dev/null || true
echo "  Done."

# ── 4. Копирование файлов ──
echo "[5/5] Copying project files..." 
echo "[5/5] Copying project files..."
rsync -avz --no-owner --no-group --no-perms -e "ssh -p ${SSH_PORT}" --exclude='node_modules' --exclude='venv' \
  --exclude='.git' --exclude='__pycache__' \
  --exclude='*.pyc' --exclude='.pytest_cache' \
  /home/xiag/real-estate-os/ "${NEW_SERVER}:/home/xiag/real-estate-os/"

rsync -avz --no-owner --no-group --no-perms -e "ssh -p ${SSH_PORT}" --exclude='node_modules' \
  /var/www/mcp-server/ "${NEW_SERVER}:/var/www/mcp-server/"

$SCP_CMD /home/xiag/real-estate-os/realtoros.dump "${NEW_SERVER}:/home/xiag/real-estate-os/realtoros.dump"
$SCP_CMD /home/xiag/real-estate-os/ttbot.sql "${NEW_SERVER}:/home/xiag/real-estate-os/ttbot.sql" 2>/dev/null || true

rsync -avz --no-owner --no-group --no-perms -e "ssh -p ${SSH_PORT}" /etc/nginx/sites-enabled/ "${NEW_SERVER}:/home/xiag/real-estate-os/nginx-sites/"

# ── 4. Генерация deploy.sh для нового сервера ──
echo "[5/5] Generating deploy script for new server..."
cat > /home/xiag/real-estate-os/deploy-on-new-server.sh << 'DEPLOY_EOF'
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
DEPLOY_EOF

$SCP_CMD /home/xiag/real-estate-os/deploy-on-new-server.sh "${NEW_SERVER}:/home/xiag/real-estate-os/deploy-on-new-server.sh"

echo ""
echo "=== Migration package sent to ${NEW_SERVER} ==="
echo ""
echo "Next steps on new server:"
echo "  ssh -p ${SSH_PORT} ${NEW_SERVER}"
echo "  bash /home/xiag/real-estate-os/deploy-on-new-server.sh"
echo ""
echo "После подтверждения работоспособности на новом сервере,"
echo "остановить старые сервисы:"
echo "  sudo systemctl stop realtoros-api"
echo "  kill \$(lsof -ti:3000)  # frontend"
