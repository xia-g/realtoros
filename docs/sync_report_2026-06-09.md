# Sync Report — 2026-06-09

## Что сделано

### 1. project_status.md — обновлён
- Добавлены Sprint 4, 5, 5.2, 6A, 6B, 7A, 7B, 8
- Включены метрики: 23,402 LOC, 669 тестов, 101 endpoint, 57 сервисов, 49 моделей
- Добавлен раздел Architecture Review Gaps (Sprint 8.5)
- **Файл:** docs/project_status.md

### 2. entities.md — синхронизирован
- Добавлены все 49 моделей с таблицами
- 8 групп: CRM (10), Lead (2), Workflow (9), Playbook (4), Knowledge (7), Regulation (8), Audit (8), Other (2)
- Актуальная схема связей (Deal — центральная сущность, 11 связанных таблиц)
- **Файл:** docs/domain/entities.md

### 3. architecture.md — обновлён
- 4 слоя: API → Services → Repositories → Models
- Domain Event Bus: 16 типов, 2 реально эмитятся, 13 dead
- MCP сервер: 20 инструментов, не видит backend
- AI Pipeline: полная цепочка
- Knowledge Graph: CRM→Graph sync НЕ ПОДКЛЮЧЕН
- **Файл:** docs/architecture/system_architecture.md

### 4. sync_docs_from_code.py — создан
- Автоматическая генерация docs/generated/ из backend-кода
- 5 генераторов: models (51), APIs (92), services, events (15 declared, 3 emitted), tests (669)
- Запуск: `python3 backend/scripts/sync_docs_from_code.py`
- Можно добавить в CI/CD
- **Файл:** backend/scripts/sync_docs_from_code.py

### 5. Event Bus — исправлен
- event_handlers.py теперь импортируется при старте Agent Runtime
- `_register_event_handlers()` добавлен в `agent.py`
- **Файл:** backend/api/routes/agent.py (+ _register_event_handlers)

### 6. backlog.json — обновлён
- Добавлена задача: «Синхронизация docs и MCP с backend-кодом» ✅
- Добавлена задача: «Доработать партиционирование» 🔲
- Добавлена задача: «Подключить Knowledge Sync» 🔲
- Добавлена задача: «Покрыть Event Bus тестами» 🔲

## Что осталось сделать руками

| # | Задача | Сложность | Приоритет |
|---|--------|-----------|-----------|
| 1 | **Реальное создание партиций в БД** (Migration 018) | Средняя | HIGH |
| 2 | **Knowledge Sync**: Client/Property/Deal services должны emit события | Средняя | HIGH |
| 3 | **Остальные 13 событий**: подключить emit в CRM-сервисах | Средняя | HIGH |
| 4 | **MCP-сервер**: зарегистрировать в Hermes Agent config.yaml | Низкая | MEDIUM |
| 5 | **Тесты Event Bus**: добавить emit→handler тесты | Средняя | MEDIUM |
| 6 | **CI/CD**: добавить sync_docs_from_code.py в pre-commit или deploy | Низкая | LOW |

## Новая версия метрик

| Метрика | До | После |
|---------|----|-------|
| project_status.md спринтов | 3 | 12 |
| entities.md моделей | ~8 | 49 |
| architecture.md слоёв | 3 (Bot→API→PG) | 4 с подуровнями |
| sync script | Нет | ✅ 5 генераторов |
| event_bus import | Только в тестах | ✅ В startup |
| backlog задач | 3 | 8 |
