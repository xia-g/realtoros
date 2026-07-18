# Развёртывание на 192.168.1.109 — мини-инструкция

## 1. На старом сервере — перенос

```bash
cd /home/xiag/real-estate-os
bash migrate.sh xiag@192.168.1.109 222
```

## 2. На новом сервере — развёртывание

```bash
# Подключиться
ssh xiag@192.168.1.109 -p 222

# Восстановить БД + установить зависимости + запустить
bash /tmp/deploy-on-new-server.sh
```

## 3. Проверка

```bash
# Backend
curl http://127.0.0.1:8090/health

# Frontend
curl http://127.0.0.1:3000

# Если nginx настроен
curl -k https://api.spcnn.ru/health
curl -k https://ai.spcnn.ru/imports/documents
```

## 4. Если что-то пошло не так

```bash
# Backend логи
journalctl -u realtoros-api -n 50 --no-pager

# Frontend перезапуск
kill $(lsof -ti:3000) 2>/dev/null
cd /home/xiag/real-estate-os/frontend && nohup npx next start --port 3000 > /tmp/next.log 2>&1 &

# Проверить PostgreSQL
pg_isready
```
