# Migration Guide: Transfer to 192.168.1.109

Полный перенос проекта RealtorOS + TTBot + MCP на новый сервер.

---

## 1. Что переносим

| Компонент | Откуда | Куда |
|-----------|--------|------|
| PostgreSQL (realtoros) | 127.0.0.1:5432 | 192.168.1.109:5432 |
| MySQL (ttbot bot) | 127.0.0.1:3306 | 192.168.1.109:3306 (опционально) |
| Backend API (uvicorn) | port 8090 | port 8090 |
| Frontend (Next.js) | port 3000 | port 3000 |
| MCP Server (Node.js) | stdio | stdio |
| Nginx configs | /etc/nginx/sites-enabled/* | /etc/nginx/sites-enabled/* |
| OCR Node endpoint | 192.168.1.113:8000 | 192.168.1.113:8000 (тот же) |

**Общий размер:** ~500 MB (без node_modules/venv — переустановить на месте)

---

## 2. Предварительные требования на сервере 1.109

```bash
# System
apt update && apt install -y postgresql nginx python3 python3-venv \
  nodejs npm redis-server

# PostgreSQL 17 (если нужна конкретная версия)
apt install -y postgresql-17 postgresql-client-17

# Node.js v22+
curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
apt install -y nodejs
```

---

## 3. Дамп и перенос БД

### 3.1. PostgreSQL (на старом сервере)

```bash
pg_dump -U realtoros -h 127.0.0.1 -d realtoros --no-owner \
  --no-acl -F c -f /tmp/realtoros.dump
```

Скопировать на новый сервер:
```bash
scp -P 222 /tmp/realtoros.dump xiag@192.168.1.109:/tmp/
```

### 3.2. Восстановить на новом сервере

```bash
sudo -u postgres psql -c "CREATE USER realtoros WITH PASSWORD 'realtoros15!';"
sudo -u postgres psql -c "CREATE DATABASE realtoros OWNER realtoros;"
sudo -u postgres psql -c "ALTER USER realtoros CREATEDB;"

pg_restore -U realtoros -h 127.0.0.1 -d realtoros \
  --no-owner --no-acl /tmp/realtoros.dump
```

### 3.3. MySQL (ttbot) — опционально

```bash
# На старом
mysqldump -u bot -pBot_Pass15 -h 127.0.0.1 bot > /tmp/ttbot.sql

# На новом
mysql -u root -p -e "CREATE DATABASE bot;"
mysql -u root -p bot < /tmp/ttbot.sql
mysql -u root -p -e "CREATE USER 'bot'@'localhost' IDENTIFIED BY 'Bot_Pass15';"
mysql -u root -p -e "GRANT ALL PRIVILEGES ON bot.* TO 'bot'@'localhost';"
```

---

## 4. Перенос кода

```bash
# Создать пользователя и группу (если нет)
sudo useradd -m -s /bin/bash xiag 2>/dev/null || true
sudo groupadd prmer 2>/dev/null || true
sudo usermod -aG prmer xiag
sudo usermod -aG prmer hermes

# Скопировать проект
rsync -avz --exclude='node_modules' --exclude='venv' \
  --exclude='.git' --exclude='__pycache__' \
  /home/xiag/real-estate-os/ xiag@192.168.1.109:/home/xiag/real-estate-os/

# MCP server
rsync -avz --exclude='node_modules' \
  /var/www/mcp-server/ xiag@192.168.1.109:/var/www/mcp-server/

# Nginx configs
rsync -avz /etc/nginx/sites-enabled/ xiag@192.168.1.109:/tmp/nginx-sites/
```

---

## 5. Установка зависимостей на новом сервере

### 5.1. Backend (Python)

```bash
cd /home/xiag/real-estate-os
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r backend/requirements.txt 2>/dev/null || pip install \
  fastapi uvicorn[standard] sqlalchemy asyncpg psycopg2-binary \
  httpx pydantic python-dotenv pydantic-settings \
  python-multipart aiofiles structlog \
  cryptography pyjwt passlib[bcrypt] \
  alembic python-dateutil

# Domain dependencies (additional)
pip install langsmith pytest pytest-asyncio pytest-mock
```

### 5.2. Frontend (Node.js)

```bash
cd /home/xiag/real-estate-os/frontend
npm ci  # или npm install
npx next build  # production build
```

### 5.3. MCP Server (Node.js)

```bash
cd /var/www/mcp-server
npm ci  # или npm install
```

---

## 6. Конфигурация

### 6.1. Environment (скопировать или создать)

```bash
# Backend
cat > /home/xiag/real-estate-os/.env << 'EOF'
DATABASE_URL=postgresql+asyncpg://realtoros:realtoros15!@127.0.0.1:5432/realtoros
APP_HOST=0.0.0.0
APP_PORT=8090
APP_DEBUG=false
SECRET_KEY=dev-secret-key-not-for-production
ACCESS_TOKEN_EXPIRE_MINUTES=1440
EOF

# TTBot
cat > /var/www/ttbot/.env << 'EOF'
DB_HOST=localhost
DB_PORT=3306
DB_NAME=bot
DB_USER=bot
DB_PASSWORD=Bot_Pass15
SERVICE_HOST=0.0.0.0
SERVICE_PORT=8000
EOF
```

### 6.2. Systemd service

```bash
cat > /etc/systemd/system/realtoros-api.service << 'SERVICEEOF'
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

systemctl daemon-reload
systemctl enable --now realtoros-api
```

### 6.3. Nginx

```bash
# Копировать конфиги и перезагрузить
cp /tmp/nginx-sites/* /etc/nginx/sites-enabled/
# Проверить и исправить server_name если нужно
nginx -t && systemctl reload nginx
```

---

## 7. Запуск сервисов

```bash
# 1. PostgreSQL
sudo systemctl start postgresql

# 2. Backend API
sudo systemctl start realtoros-api
curl http://127.0.0.1:8090/health  # должно вернуть OK

# 3. Frontend
cd /home/xiag/real-estate-os/frontend
nohup npx next start --port 3000 > /tmp/next.log 2>&1 &
curl http://127.0.0.1:3000  # должно вернуть 308 (редирект)

# 4. MCP Server (stdio — запускается через Hermes/агента)
cd /var/www/mcp-server
node server.js  # тестовый запуск, Ctrl+C

# 5. Проверка всех endpoints
curl -k https://api.spcnn.ru/health
curl -k https://ai.spcnn.ru/imports/documents
```

---

## 8. Порядок переноса (checklist)

- [ ] **Новый сервер**: установить пакеты (п. 2)
- [ ] **Старый сервер**: дамп PostgreSQL (п. 3.1)
- [ ] **Новый сервер**: восстановить PostgreSQL (п. 3.2)
- [ ] **Старый → новый**: rsync кода (п. 4)
- [ ] **Новый сервер**: создать venv, npm ci (п. 5)
- [ ] **Новый сервер**: скопировать .env (п. 6.1)
- [ ] **Новый сервер**: настроить systemd (п. 6.2)
- [ ] **Новый сервер**: настроить nginx (п. 6.3)
- [ ] **Новый сервер**: запустить всё (п. 7)
- [ ] **Старый сервер**: выключить сервисы (когда новый подтверждён)

---

## 9. Port mapping

| Порт | Сервис | Назначение |
|------|--------|------------|
| 5432 | PostgreSQL | Основная БД |
| 3306 | MySQL | TTBot БД (опционально) |
| 8090 | uvicorn | Backend API (api.spcnn.ru) |
| 3000 | Next.js | Frontend (ai.spcnn.ru) |
| 80/443 | nginx | Reverse proxy для всех поддоменов |

---

## 10. Траблшутинг

**Backend не стартует:**
```bash
journalctl -u realtoros-api -n 50 --no-pager
```

**Postgres не принимает соединения:**
```bash
# Проверить pg_hba.conf
grep -n "realtoros" /etc/postgresql/17/main/pg_hba.conf
# Должно быть: host realtoros realtoros 127.0.0.1/32 md5
```

**Next.js не стартует (EADDRINUSE):**
```bash
kill $(lsof -ti:3000) 2>/dev/null; sleep 1; npx next start --port 3000
```

**Nginx 502 Bad Gateway:**
```bash
# Проверить что бэкенд жив
curl http://127.0.0.1:8090/health
# Проверить логи nginx
tail -20 /var/log/nginx/error.log
```
