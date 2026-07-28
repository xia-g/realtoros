# Epic 3 — Product Layer Alignment Report

> **Дата:** 2026-07-28
> **Аналитик:** Hermes Agent (Architect Assistant)
> **Контекст:** Анализ несоответствий между текущей реализацией Product Layer (promote-to-deal pipeline, DCR consumer, KR consumer) и утверждённой архитектурой Epic 3 (`docs/architecture/epic3-freeze-record.md`)
> **Источники данных:** Код, БД (document_intake, documents, deals, event_outbox, consumer_processed_events), freeze record, verification report

---

## 1. Соответствие архитектуре — что работает как задумано

### 1.1 Event Backbone — работает полностью

| Компонент | Статус | Доказательство |
|-----------|--------|----------------|
| Document Lifecycle pipeline → READY | ✅ | Документ `a2743303...` в статусе `READY`, `pipeline_stage = completed` |
| Outbox enqueue (одна транзакция) | ✅ | `event_outbox` содержит событие `document.ready` |
| Publisher доставка | ✅ | Событие помечено `published` |
| Consumer Framework (BaseConsumer) | ✅ | Все 3 consumer'а зарегистрированы |
| Consumer-уровневая идемпотентность | ✅ | `consumer_processed_events` — по 1 записи на каждого |
| GraphSyncConsumer — graph_nodes | ✅ | 1 graph_node типа `Document` создан |

### 1.2 Consumers зарегистрированы корректно

Все 4 consumer'а зарегистрированы в `main.py` на правильные event types:

| Consumer | Event | Регистрация |
|----------|-------|-------------|
| GraphSyncConsumer | document.*, client.*, property.*, deal.*, lead.* | ✅ |
| DealContextResolutionConsumer | document.ready | ✅ |
| KnowledgeRuntimeConsumer | document.ready | ✅ |
| DealAccountingConsumer | deal.accounting_ready | ✅ |

### 1.3 Архитектурные решения (ADR) — код соответствует плану

| ADR | Статус | Подтверждение |
|-----|--------|---------------|
| DCR ADR-001: Отдельный consumer | ✅ | DealContextResolutionConsumer, не GraphSyncConsumer |
| DCR ADR-004: Reuse CandidateFinder | ✅ | DealContextResolver использует CandidateFinder |
| DCR ADR-005: Confidence-based resolution | ✅ | RESOLVED / AMBIGUOUS / NOT_FOUND |
| DCR ADR-006: Deal через ApplicationService | ✅ | DealApplicationService, не прямой SQL |
| KR ADR-001: Один consumer | ✅ | KnowledgeRuntimeConsumer делегирует сервису |
| ACC ADR-001: DealAccountingConsumer | ✅ | Код написан, зарегистрирован |

---

## 2. Несоответствия Product Layer

### 2.1 [Blocker] ID mismatch — DCR ищет Deal.id == document_id, но ID не совпадают

**Файл:** `backend/infrastructure/consumers/deal_context_resolution_consumer.py`, строка 157

**Функция:** `_find_deal_by_document()`

**Ожидание по архитектуре:** DCR обрабатывает `document.ready`, находит сделку, ассоциированную с документом, и разрешает контекст. Архитектура предполагает наличие сделки, но не специфицирует механизм связи.

**Реальность:** Consumer выполняет:
```python
stmt = select(Deal).where(Deal.id == document_id)
```
где `document_id` = `event.aggregate_id` = `document_intake.document_id`.

**Проблема:** `document_id` из события (`a2743303-178a-40bf-bb07-3b380db2dc2d`) НЕ равен `deals.id`, который создаётся `promote_to_deal` как новый случайный UUID (`4e7082a1-4f73-4d5b-94eb-2f6eb597c994`).

| Сущность | Поле | Значение |
|----------|------|----------|
| document_intake | document_id | `a2743303-178a-40bf-bb07-3b380db2dc2d` |
| event_outbox | aggregate_id | `a2743303-178a-40bf-bb07-3b380db2dc2d` (то же) |
| deal (promote_to_deal) | id | `4e7082a1-4f73-4d5b-94eb-2f6eb597c994` (новый UUID) |
| DCR search | Deal.id | ищет `a2743303...` — не находит |

**Цепочка последствий:**
```
DCR: Deal not found → exit
  └── _emit_accounting_ready() NEVER called
      └── Deal.accounting_ready NOT emitted
          └── DealAccountingConsumer NEVER fires
```

**Исправление:** Consumer должен искать сделку не по `Deal.id == document_id`, а через связующую таблицу (например, `deal_document_packages` или `documents.deal_id`). Корректный lookup:
1. Найти `documents` запись, где `documents.file_hash` соответствует `document_intake.checksum` (или другой идентификатор)
2. Получить `documents.deal_id` → это и есть ID сделки
3. Либо добавить в `document_intake` колонку `promoted_deal_id` и искать по ней

---

### 2.2 [High] Dual document tables — KnowledgeRuntimeService ищет в `documents`, данные в `document_intake`

**Файл:** `backend/services/knowledge_runtime/service.py`, строка 104-107

**Функция:** `_load_document()`

**Ожидание по архитектуре:** KR ADR-002: «consumer loads data from DB, not from event payload». Consumer загружает документ из БД по `document_id` из события.

**Реальность:**
```python
result = await session.execute(
    select(Document).where(Document.id == document_id)
)
```
`Document` модель маппится на таблицу `documents`. Но:

- **Pipeline пишет данные** в `document_intake` (Epic 1, Product Layer) — через `DocumentRepository` из `document_lifecycle.py` (строка 246: `INSERT INTO document_intake`)
- **KnowledgeRuntimeService читает** из `documents` (Epic 3 SQLAlchemy модель) — пустая или содержит записи, созданные `promote_to_deal`
- **event.aggregate_id** содержит `document_intake.document_id`, который не совпадает ни с одним `documents.id`

| Таблица | Записи | Популяция | Читатель |
|---------|--------|-----------|----------|
| `document_intake` | 1 запись (READY) | DocumentLifecycle pipeline | DocumentRepository (Epic 1) |
| `documents` | 3 записи | promote_to_deal route | KnowledgeRuntimeService (Epic 3) |
| `documents.id` | `394f5421...`, `84142eb0...`, `6119dbea...` | NEW UUID, не связаны с document_intake | — |

**Последствие:** KnowledgeRuntimeService не находит документ → логирует `knowledge_runtime_document_not_found` → не создаёт graph node, не генерирует embeddings, не обновляет search index.

**Исправление:** Один из вариантов:
1. **(Рекомендуемый)** Переключить `KnowledgeRuntimeService._load_document()` на чтение из `document_intake` через `DocumentRepository` (Epic 1), т.к. именно там живут данные после pipeline
2. Либо синхронизировать: после `mark_document_ready()` создавать/обновлять запись в `documents` таблице (но это дублирование данных)

---

### 2.3 [High] Отсутствие `deal.accounting_ready` — DealAccountingConsumer не срабатывает

**Файл:** `backend/infrastructure/consumers/deal_context_resolution_consumer.py`, строка 231-275

**Функция:** `_emit_accounting_ready()`

**Ожидание по архитектуре:** После успешного разрешения контекста сделки (DCR) consumer эмитит `deal.accounting_ready`. DealAccountingConsumer подписан на это событие и создаёт AccountingDocument.

**Реальность:** `_emit_accounting_ready()` никогда не вызывается, потому что:

1. DCR consumer не находит сделку (см. 2.1 — ID mismatch) → выход на строке 96
2. `_emit_accounting_ready()` вызывается только на строке 136, ПОСЛЕ успешного `resolver.apply()`
3. `deal.accounting_ready` событие не попадает в event_outbox
4. DealAccountingConsumer никогда не активируется

**Проверка в БД:**
- `event_outbox`: только `document.ready` — нет `deal.accounting_ready`
- `consumer_processed_events`: нет записей `deal_accounting`
- `business_events`: 0 записей

**Дополнительная проблема:** Даже если DCR найдёт сделку, `deal.price = 0.00`, `deal.commission = 0.00`, `deal.deposit_amount = 0.00` — `_emit_accounting_ready()` передаст нулевые значения (см. 2.5).

**Исправление:** Не изолированное — зависит от исправления 2.1. После того как DCR находит сделку:
- Убедиться, что `deal.price`, `deal.commission`, `deal.deposit_amount` заполнены (из профиля документа)
- `_emit_accounting_ready()` будет вызван естественным путём

---

### 2.4 [Medium] promote_to_deal создаёт документ в `documents` с новым UUID — потеря связи с event

**Файл:** `backend/api/routes/promote_to_deal.py`, строки 210, 242-249

**Ожидание:** После promote_to_deal должен быть установлен канонический ID, по которому consumer'ы могут найти сделку по документу.

**Реальность:** `promote_to_deal`:
1. Создаёт сделку с `deal_id = str(uuid.uuid4())` (строка 210) — новый случайный UUID
2. Создаёт запись в `documents` с `doc_id = str(uuid.uuid4())` (строка 242) — ещё один новый UUID
3. Обновляет `accounting.document_intake.promoted_deal_id = deal_id` (строка 239)
4. НЕ обновляет `public.document_intake` (Epic 1 таблица)

**Проблема:** Цепочка идентификации разорвана:
```
document_intake.document_id = a2743303...
    ↓ event.aggregate_id
documents.id = 394f5421... (совсем другой UUID)
    ↓ documents.deal_id
deals.id = 4e7082a1... (ещё один UUID)
```

У consumer'ов (DCR, KR) нет способа пройти от `event.aggregate_id` к `deals.id`, потому что:
- Нет таблицы, связывающей `document_intake.document_id` с `deals.id`
- `accounting.document_intake.promoted_deal_id` существует, но consumer'ы его не читают
- `documents` таблица не связана с `document_intake` (разные UUID)

**Исправление:** Добавить колонку `promoted_deal_id` в `public.document_intake`. При promote_to_deal заполнять её. DCR consumer должен читать `document_intake.promoted_deal_id` для поиска сделки, а не предполагать `Deal.id == document_id`.

---

### 2.5 [Medium] Дефолтные нулевые финансовые поля на сделке

**Файл:** `backend/api/routes/promote_to_deal.py`, строки 212-215, 229-235

**Ожидание:** Deal создаётся с реальными ценами из документа (price, commission, deposit).

**Реальность:**
```python
price = 0.0  # строка 212 — только если нет amounts в полях
# ...
INSERT INTO public.deals (... commission, deposit_amount ...)
VALUES (..., 0.0, 0.0)  # строки 229-235
```

**Проверка в БД:** `deal.price = 0.00`, `deal.commission = 0.00`, `deal.deposit_amount = 0.00`

Даже если DCR найдёт сделку (проблема 2.1 исправлена), `_emit_accounting_ready()` отправит `deal.accounting_ready` с нулевыми значениями. DealAccountingConsumer создаст AccountingDocument с нулевыми суммами.

**Исправление:** Заполнять `price`, `commission`, `deposit_amount` из профиля документа (extracted_fields.amounts, financial_terms) при создании сделки. Или добавить шаг обновления цен после DCR resolution.

---

### 2.6 [Medium] sequence: document.ready происходит ДО promote_to_deal

**Файлы:** `backend/api/routes/processing.py` → `backend/api/routes/promote_to_deal.py`

**Ожидание:** DCR consumer должен найти существующую сделку при обработке `document.ready`.

**Реальность (из verification report и кода):** Pipeline выполняется сразу после загрузки документа. Документ переходит в READY → `document.ready` эмитится → consumer'ы получают событие. `promote_to_deal` — это отдельный endpoint, который вызывается UI/оператором ПОСЛЕ pipeline. Когда DCR consumer обрабатывает `document.ready`, сделка ещё не создана.

**Последствие:** Даже если исправить ID lookup (2.1), сделки всё равно не будет на момент обработки события — архитектурно событие `document.ready` приходит до `promote_to_deal`.

**Исправление на уровне архитектуры:**
1. **Создавать сделку ДО pipeline** — при загрузке документа (UPLOADED → deal candidate)
2. **Изменить триггер event** — эмитить `document.ready` только ПОСЛЕ того, как сделка создана и привязана
3. **Использовать механизм re-delivery** — если DCR не находит сделку, не выходить тихо, а использовать retry, чтобы повторно обработать событие после promote_to_deal (НО это нарушает текущую retry policy — только 3 попытки)
4. **Эмитить отдельное событие** `deal.document_attached` после promote_to_deal, на которое подписать DCR consumer

---

## 3. Canonical ID map

| Пространство | Таблица | Поле ID | Тип | Значение (пример) |
|-------------|---------|---------|-----|-------------------|
| **Epic 1 — Document Intake** | `public.document_intake` | `document_id` | text (UUID) | `a2743303-178a-40bf-bb07-3b380db2dc2d` |
| **Epic 1 — Accounting Intake** | `accounting.document_intake` | `id` | text | `6854907c-25d4-4007-bbc2-63eb2fe35651` |
| **Epic 3 — Document model** | `public.documents` | `id` | uuid | `394f5421-1400-4750-aa51-4e329a19bb58` |
| **Epic 3 — Deal** | `public.deals` | `id` | uuid | `4e7082a1-4f73-4d5b-94eb-2f6eb597c994` |
| **Event outbox** | `event_outbox` | `aggregate_id` | uuid | `a2743303-178a-40bf-bb07-3b380db2dc2d` (= document_intake.document_id) |
| **Promoted deal link** | `accounting.document_intake` | `promoted_deal_id` | text | `4e7082a1-4f73-4d5b-94eb-2f6eb597c994` |

### Связи (как есть сейчас)

```
document_intake.document_id (a2743303...)
  ├──→ event_outbox.aggregate_id (тот же)     ← это знают consumer'ы
  ├──→ accounting.document_intake (другая БД!) ← через file_hash / checksum
  └──→ ❌ НЕТ связи с deals.id

documents.id (394f5421...) — создан promote_to_deal
  └──→ documents.deal_id → deals.id (4e7082a1...)

deals.id (4e7082a1...) — создан promote_to_deal
  └──→ accounting.document_intake.promoted_deal_id
```

### Что должно быть (canonical)

```
document_intake.document_id (a2743303...)
  ├──→ event_outbox.aggregate_id
  ├──→ document_intake.promoted_deal_id → deals.id (НОВОЕ ПОЛЕ)
  ├──→ documents.file_hash ↔ document_intake.checksum (связь таблиц)
  └──→ Accounting: отдельная таблица document_deal_binding
```

---

## 4. Минимальный набор исправлений

### 🔴 Fix 1: ID lookup в DCR consumer — первоочередной

**Файл:** `backend/infrastructure/consumers/deal_context_resolution_consumer.py`

**Изменение:** В `_find_deal_by_document()` заменить `select(Deal).where(Deal.id == document_id)` на:
1. Прочитать `document_intake.promoted_deal_id` по `document_id` (нужна новая колонка или через `accounting.document_intake`)
2. Либо: найти `documents` запись, где `documents.file_hash == document_intake.checksum` → взять `documents.deal_id`
3. Либо: найти `deal_document_packages` по `document_id` → получить `deal_id`

**Затрагивает:** Только DCR consumer

---

### 🔴 Fix 2: KnowledgeRuntimeService — читать из правильной таблицы

**Файл:** `backend/services/knowledge_runtime/service.py`

**Изменение:** В `_load_document()` заменить `select(Document).where(Document.id == document_id)` на загрузку из `document_intake` через `DocumentRepository` (Epic 1). Это даст:
- Доступ к полному профилю документа (seller, buyer, price)
- Возможность создавать document_chunks и embeddings из реальных данных

**Альтернатива:** Синхронизировать `documents` таблицу при `mark_document_ready()` — но это дублирование.

**Затрагивает:** KnowledgeRuntimeService (не consumer, а сервис)

---

### 🟡 Fix 3: Добавить промоцию deal в document_intake

**Файл:** `backend/api/routes/promote_to_deal.py`

**Изменение:** После создания сделки (строка 235), обновить `public.document_intake`:
```sql
UPDATE document_intake SET promoted_deal_id = $1 WHERE document_id = $2
```
(Аналогично тому, что уже делается для `accounting.document_intake` на строке 238)

**Затрагивает:** promote_to_deal route + DCR consumer (связующий механизм)

---

### 🟡 Fix 4: Цены из профиля документа

**Файл:** `backend/api/routes/promote_to_deal.py`

**Изменение:** При создании deal заполнять `price`, `commission` (0.0 пока), `deposit_amount` (0.0 пока) из `extracted_fields.amounts` или `fields`. Использовать `max(amounts)` как цену, если доступно.

**Затрагивает:** promote_to_deal route

---

### 🟢 Fix 5: Sequence — document.ready после promote_to_deal

**Изменение на уровне архитектуры (требует ADR):** Не эмитить `document.ready` сразу после pipeline. Вместо этого:
1. Pipeline завершается → статус ANALYZED (не READY)
2. `promote_to_deal` создаёт сделку
3. После привязки к сделке → эмитится `document.ready`
4. Или после promote_to_deal эмитить `deal.document_attached`, который DCR слушает вместо `document.ready`

**Затрагивает:** Архитектурное решение — требуется ADR. Не входит в минимальный набор.

---

## 5. После исправления — ожидаемый E2E flow

```
Upload → Pipeline (OCR→Class→Extract→Knowledge) → ANALYZED
  ↓
promote_to_deal
  ├── Создаёт deal (price из профиля документа)
  ├── Создаёт document в documents таблице
  ├── Обновляет document_intake.promoted_deal_id
  └── Эмитит document.ready (или deal.document_attached)
  ↓
Event Publisher → Consumers:
  ├── GraphSyncConsumer: ✅ создаёт graph_node
  ├── DealContextResolutionConsumer:
  │   ├── _find_deal_by_document: находит deal через promoted_deal_id
  │   ├── Resolves: Property, Client, Participants
  │   ├── Обновляет deal (property_id)
  │   ├── Эмитит deal.updated
  │   └── Эмитит deal.accounting_ready
  ├── KnowledgeRuntimeConsumer:
  │   ├── Загружает документ из document_intake
  │   ├── Создаёт graph_node
  │   ├── Создаёт document_chunks
  │   └── Генерирует embeddings
  └── DealAccountingConsumer (на deal.accounting_ready):
      ├── Создаёт AccountingDocument (commission + deposit)
      └── Status = READY
```

### Проверка после исправлений

| Consumer | Критерий | Метод проверки |
|----------|----------|----------------|
| DCR | `consumer_processed_events` +1 | `SELECT COUNT(*) FROM consumer_processed_events WHERE consumer_name = 'deal_context_resolution'` |
| DCR | Clients/properties созданы | `SELECT * FROM clients` / `SELECT * FROM properties` |
| DCR | Deal обновлён | `SELECT property_id FROM deals WHERE id = ...` — не NULL |
| DCR | `deal.accounting_ready` | `SELECT * FROM event_outbox WHERE event_type = 'deal.accounting_ready'` |
| KR | Graph node создан | `SELECT * FROM graph_nodes WHERE source_entity_type = 'document'` |
| KR | Document chunks | `SELECT * FROM document_chunks WHERE document_id = ...` |
| KR | Embeddings | `SELECT * FROM embeddings WHERE document_id = ...` |
| ACC | AccountingDocument | `SELECT * FROM accounting_documents WHERE deal_id = ...` |

---

## 6. Заключение

### Оценка: ⚠️ PARTIAL — код реализован, но Product Layer разрывает связи

Epic 3 архитектурно корректен: Event Backbone работает, Consumers зарегистрированы, BaseConsumer с идемпотентностью функционирует. **Проблемы — в интеграции Product Layer (Epic 1) с Epic 3 consumers.**

### Корень проблем

Три проблемы сводятся к одной: **разрыв идентификации** между `document_intake` (Epic 1) и `deals` + `documents` (Epic 3).

| Проблема | Причина | Серьёзность |
|----------|---------|-------------|
| DCR не находит deal | `Deal.id != document_id` — разные UUID | 🔴 Blocker |
| KR не находит документ | Читает `documents` (Epic 3), данные в `document_intake` (Epic 1) | 🔴 Blocker |
| Нет deal.accounting_ready | Зависит от DCR (каскадный сбой) | 🔴 Blocker |
| promote_to_deal не связывает таблицы | Не обновляет `public.document_intake`, только `accounting.document_intake` | 🟡 High |
| Нулевые финансовые данные | `promote_to_deal` не заполняет price/commission/deposit | 🟡 Medium |
| document.ready до promote_to_deal | Sequence — событие приходит до создания сделки | 🟡 Medium |

### Минимальные изменения для E2E работоспособности

1. **DCR ID lookup** — искать deal через `document_intake.promoted_deal_id`, а не через `Deal.id == document_id`
2. **KR document source** — переключиться на `document_intake` вместо `documents`
3. **promote_to_deal** — обновлять `public.document_intake.promoted_deal_id` (как уже делает для `accounting.document_intake`)
4. **promote_to_deal** — заполнять price из extracted_fields

### Что НЕ требует изменений

- Event Backbone (Outbox, Publisher, Consumer Framework) — ✅ работает
- GraphSyncConsumer — ✅ работает
- Consumer регистрация в `main.py` — ✅ корректна
- BaseConsumer идемпотентность — ✅ работает
- DCR resolver (CandidateFinder, DealContextResolver) — ✅ код корректен
- KnowledgeRuntimeService pipeline — ✅ код корректен, проблема в источнике данных
- DealAccountingConsumer — ✅ код корректен, проблема в отсутствии события

---

*Конец отчёта. Epic 3 — Product Layer Alignment Report.*
