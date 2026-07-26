# Отчёт: Соответствие фронтенда (Import Wizard) новому бэку после Epic 3

## 1. Import Wizard — структура

**Файл:** `frontend/app/imports/documents/page.tsx` (812 строк)
**Шаги (7):** `select → upload → ocr → analyze → deal → deal_created → done`

### API вызовы Import Wizard

| Шаг | Endpoint | Метод | Backend файл | Статус |
|-----|----------|-------|-------------|--------|
| select | `GET /api/v1/companies` | fetch | — | ✅ |
| upload | `POST /api/v1/upload/document` | FormData | `api/routes/uploads.py` | ✅ |
| ocr | `GET /api/v1/upload/job/{job_id}` | poll (3s) | `api/routes/uploads.py` | ✅ |
| analyze | `GET /api/v1/deals?company_id=` | fetch | — | ✅ |
| deal | `POST /api/v1/documents/{id}/promote-to-deal` | fetch | `api/routes/promote_to_deal.py` | ✅ |
| deal | `POST /api/v1/documents/{id}/bind-to-deal/{deal_id}` | fetch | `api/routes/promote_to_deal.py` | ✅ |

**Вывод:** Import Wizard использует `POST /api/v1/upload/document` (OCR Node pipeline), что соответствует Epic 3. ✅

---

## 2. API Contract — проверка критических endpoint'ов

### Существующие backend endpoints

| Endpoint | Существует | Файл |
|----------|-----------|------|
| `POST /api/v1/documents/{id}/mark-ready` | ✅ | `api/routes/documents.py:208` |
| `POST /api/v1/documents/{id}/promote-to-deal` | ✅ | `api/routes/promote_to_deal.py:144` |
| `POST /api/v1/documents/{id}/bind-to-deal/{deal_id}` | ✅ | `api/routes/promote_to_deal.py:350` |
| `GET /api/v1/documents/{id}/status` | ✅ | `api/routes/documents.py:115` |
| `POST /api/v1/documents/upload` | ✅ | `api/routes/documents.py:69` |
| `POST /api/v1/documents/{id}/transition` | ✅ | `api/routes/documents.py:134` |
| `POST /api/v1/processing/pipelines/start/{id}` | ✅ | `api/routes/processing.py:34` |

### Frontend api-client.ts — недостающие endpoint'ы

В `frontend/lib/api-client.ts` определены:

```typescript
endpoints.document: (id) => `/api/v1/documents/${id}`
endpoints.documentValidate: (id) => `/api/v1/documents/${id}/validate`
endpoints.uploadDocument: '/api/v1/upload/document'
```

**НЕ определены:**
- ❌ `markReady` — нет
- ❌ `documentStatus` — нет (целиком)
- ❌ `documentTransition` — нет
- ❌ `promoteToDeal` — нет (используется raw fetch в Import Wizard)
- ❌ `bindToDeal` — нет (используется raw fetch)

**Вывод:** api-client.ts не покрывает document lifecycle endpoints. Import Wizard использует `fetch()` напрямую, минуя клиент.

---

## 3. Document Lifecycle — критическое расхождение

### Backend lifecycle (VALID_TRANSITIONS)

```
UPLOADED → VALIDATED → ACCEPTED → PROCESSING → ANALYZED → READY → ROUTED → ARCHIVED
```

### Как Import Wizard проходит lifecycle

```
[UPLOAD] → [OCR] → [ANALYZE] → [DEAL]
   │          │          │          │
   │          │          │          └→ promote-to-deal (создаёт сделку в БД)
   │          │          │
   │          │          └→ analyzeDocument() — клиентский JS, без вызова API
   │          │
   │          └→ pollJob() — GET /upload/job/{id} — ждёт OCR Node
   │
   └→ POST /upload/document → OCR Node (сохраняет в accounting.document_intake)
```

### 🔴 КРИТИЧЕСКИЕ ПРОБЛЕМЫ

1. **Никогда не вызывается `POST /documents/{id}/mark-ready`**
   После того как Import Wizard создаёт сделку (deal_created/done), документ остаётся в `accounting.document_intake` со статусом `pending` или `completed` — он **НЕ переводится** в статус `READY` в lifecycle-таблице `document_intake`.

2. **Все 4 Event Backbone consumer'а НИКОГДА не сработают** для документов, загруженных через Import Wizard.

   Документ.ready эмитится ТОЛЬКО внутри `mark_document_ready()` (`services/document_lifecycle.py:111`), который вызывается из `POST /documents/{id}/mark-ready`. Этот endpoint **не вызывается** фронтом.

3. **Два разных document_intake** — Import Wizard сохраняет в `accounting.document_intake` (через OCR upload pipeline), а lifecycle endpoints читают/пишут из `document_intake` (без схемы accounting). Это **разные таблицы** — документ, прошедший через Import Wizard, НЕВОЗМОЖНО перевести по lifecycle через стандартные endpoints.

4. **Фронт не отображает lifecycle статусы** после ANALYZED:
   - Нет кнопки "mark-ready"
   - Нет `GET /documents/{id}/status`
   - Нет проверки разрешённых переходов
   - Нет индикаторов `READY`, `ROUTED`, `ARCHIVED`

5. **`analyzeDocument()` — клиентский JS, не API** — фронт сам классифицирует документы (hardcoded mapping), вместо вызова `POST /processing/pipelines/start/{id}`.

---

## 4. Event Backbone — изоляция

```
FRONTEND ──→ API ENDPOINTS ──→ EVENT PUBLISHER (outbox) ──→ CONSUMERS
   │                               │
   │                               ├── document.ready → DealContextResolutionConsumer
   │                               ├── document.ready → KnowledgeRuntimeConsumer
   │                               ├── document.ready → GraphSyncConsumer (все типы)
   │                               └── deal.accounting_ready → DealAccountingConsumer
```

**Ситуация с изоляцией: ✅ ХОРОШО**
Фронт НИГДЕ не вызывает Event Backbone напрямую. Все события эмитятся сервером через outbox механизм.

**НО:** Поскольку `document.ready` никогда не эмитится (см. п.3), консьюмеры фактически не срабатывают для документов из Import Wizard.

### 4 consumer'а (все зарегистрированы в `main.py`)

| Consumer | Событие | Назначение |
|----------|---------|-----------|
| GraphSyncConsumer | Все типы событий | Синхронизация графа знаний |
| DealContextResolutionConsumer | `document.ready` | Разрешение Property/Client из профиля |
| KnowledgeRuntimeConsumer | `document.ready` | Семантическое индексирование |
| DealAccountingConsumer | `deal.accounting_ready` | Создание AccountingDocument |

---

## 5. Сводка расхождений

| Аспект | Статус | Описание |
|--------|--------|----------|
| Import Wizard вызывает правильные OCR endpoints | ✅ | Использует `/api/v1/upload/document` (OCR Node) |
| promote-to-deal работает | ✅ | Оба endpoint'а существуют и корректно вызываются |
| bind-to-deal работает | ✅ | Endpoint существует |
| mark-ready endpoint существует на бэке | ✅ | `POST /documents/{id}/mark-ready` есть |
| **mark-ready НИКОГДА не вызывается** | 🔴 | Фронт не вызывает — событие `document.ready` не эмитится |
| **Event Backbone consumer'ы не срабатывают** | 🔴 | Нет события `document.ready` → все 4 consumer'а без работы |
| **Две разных document_intake таблицы** | 🔴 | `accounting.document_intake` (OCR) vs `document_intake` (lifecycle) |
| api-client.ts не покрывает lifecycle | 🟡 | Нет `markReady`, `documentStatus`, `documentTransition` |
| `analyzeDocument()` клиентский | 🟡 | Hardcoded маппинг типов на фронте вместо API |
| Нет отображения статусов READY/ROUTED/ARCHIVED | 🟡 | Фронт не показывает lifecycle статусы после ANALYZED |
| Изоляция Event Backbone | ✅ | Фронт не вызывает backbone напрямую |

---

## 6. Рекомендации

### 🔴 Критические (блокирующие Epic 3)

1. **Добавить вызов `POST /documents/{id}/mark-ready`** после успешного создания сделки (step `deal_created`). Этот вызов должен перевести документ из `accounting.document_intake` в lifecycle `document_intake` и эмитнуть `document.ready`.

2. **Унифицировать `document_intake`** — решить проблему двух таблиц. Либо OCR pipeline должен писать в `document_intake` (lifecycle), либо lifecycle endpoints должны читать из `accounting.document_intake`.

3. **Добавить кнопку "Подтвердить / Mark as Ready"** на странице документа или в Import Wizard после завершения OCR+анализа.

### 🟡 Важные

4. **Добавить в `api-client.ts`** недостающие endpoints: `markReady`, `documentStatus`, `documentTransition`, `promoteToDeal`, `bindToDeal`.

5. **Заменить `analyzeDocument()`** клиентский JS на вызов `POST /processing/pipelines/start/{id}`.

6. **Добавить отображение lifecycle статуса** на странице документа и в списке документов — с отображением разрешённых переходов.

7. **Добавить `GET /documents/{id}/status`** на страницу документа для показа текущего статуса и возможных действий.

---

*Отчёт создан: 26 июля 2026*
*Проверенные файлы:*
- `frontend/app/imports/documents/page.tsx` (Import Wizard, 812 строк)
- `frontend/lib/api-client.ts` (API клиент, 171 строка)
- `frontend/app/documents/page.tsx` (список документов, 43 строки)
- `frontend/app/documents/[id]/page.tsx` (профиль документа, 257 строк)
- `backend/api/routes/documents.py` (lifecycle endpoints, 270 строк)
- `backend/api/routes/uploads.py` (OCR upload pipeline, 655 строк)
- `backend/api/routes/promote_to_deal.py` (promote/bind endpoints, 459 строк)
- `backend/api/routes/processing.py` (pipeline, 192 строки)
- `backend/services/document_lifecycle.py` (lifecycle transitions, 364 строки)
- `backend/infrastructure/consumers/` (4 consumer'а)
- `backend/main.py` (регистрация consumer'ов)
