# Epic 3 — Architecture Review (Product Layer Alignment)

> **Дата:** 2026-07-28
> **Аналитик:** Hermes Agent (Architect Assistant)
> **Контекст:** Определение последовательности событий, canonical identity, root cause и Proposal минимальных исправлений.
> **Источники:** Freeze Record, DCR Proposal, Alignment Report, Verification Report, код, БД.

---

## 0. Ключевой вопрос: последовательность событий

### Доказательство: document.ready происходит ДО создания сделки

**Фактическая последовательность в коде:**

```
Upload → Pipeline (OCR→Class→Extract→Knowledge) → READY → document.ready
    ↓                                                                     
  (промежуток времени — UI/оператор вызывает promote_to_deal)             
    ↓                                                                     
promote_to_deal → создаёт deal + document в БД                           
```

**Доказательство:**

1. **`backend/api/routes/processing.py:118`** — `mark_document_ready(doc)` вызывается сразу после успешного pipeline. Документ переходит в READY → эмитится `document.ready`.

2. **`backend/api/routes/promote_to_deal.py:144-145`** — `POST /documents/{id}/promote-to-deal` — отдельный endpoint, вызываемый UI. Создаёт сделку с новым UUID.

3. **Freeze Record (раздел 1, Event Flow Detail):**
   ```
   document.ready
     ├── GraphSyncConsumer
     ├── DealContextResolution    ← ожидает, что сделка УЖЕ существует
     │   └── deal.updated
     │   └── deal.accounting_ready
     └── KnowledgeRuntimeConsumer
   ```
   Архитектура Freeze Record фиксирует, что DCR обрабатывает `document.ready` и находит сделку — но **не специфицирует, как сделка должна быть создана до этого момента**.

4. **DCR Proposal (раздел 1.1, строка 15):**
   > "After `POST /documents/{id}/promote-to-deal`, the newly created Deal is a **skeleton** with critical gaps"
   
   DCR Proposal явно предполагает, что promote-to-deal выполняется **до** обработки document.ready.

5. **DCR Proposal (раздел 3.1, строка 118 — ожидаемая имплементация):**
   > "Find the target Deal via `document_intake.promoted_deal_id`"
   
   Proposal предполагает lookup через `promoted_deal_id` — НО в реальном коде (строка 157):
   ```python
   stmt = select(Deal).where(Deal.id == document_id)
   ```
   Используется `Deal.id == document_id` — это работает ТОЛЬКО если deal.id == document_intake.document_id, что никогда не выполняется.

### Вывод: архитектурный пробел

**Freeze Record НЕ специфицирует жизненный цикл создания сделки относительно document.ready.** Событие document.ready эмитится сразу после pipeline, а сделка создаётся позже через UI. Это не нарушение Freeze (Freeze об этом ничего не говорит), но это **архитектурный пробел**, который блокирует весь downstream — DCR, KR, ACC.

---

## 1. Canonical Identity Map

| Пространство | Таблица | Поле ID | Тип | Значение (пример) |
|---|---|---|---|---|
| **Epic 1 — Document Intake** | `public.document_intake` | `document_id` | text (UUID) | `a2743303-178a-40bf-bb07-3b380db2dc2d` |
| **Epic 3 — Document model** | `public.documents` | `id` | uuid | `394f5421-1400-4750-aa51-4e329a19bb58` |
| **Epic 3 — Deal** | `public.deals` | `id` | uuid | `4e7082a1-4f73-4d5b-94eb-2f6eb597c994` |
| **Event outbox** | `event_outbox` | `aggregate_id` | uuid | `a2743303-...` (= document_intake.document_id) |
| **Promoted deal link (accounting)** | `accounting.document_intake` | `promoted_deal_id` | uuid | `4e7082a1-...` |
| **Promoted deal link (public)** | `public.document_intake` | ❌ **ОТСУТСТВУЕТ** | — | — |
| **Document-Deal link** | `deal_document_packages` | `document_id` + `deal_id` | uuid | `394f5421...` + `4e7082a1...` |

### Связи (как есть сейчас)

```
document_intake (public).document_id = a2743303-...
  ├──→ event_outbox.aggregate_id (тот же UUID)
  ├──→ ❌ НЕТ promoted_deal_id (нужная колонка отсутствует!)
  └──→ checksum = 58f77995...
         │
         ▼
accounting.document_intake: ищется по file_hash = checksum
  └──→ promoted_deal_id = 4e7082a1-...  ← это знает accounting, НО НЕ consumer'ы

promote_to_deal создаёт:
  ├── deals.id = 4e7082a1-... (НОВЫЙ UUID, не связан с a2743303-...)
  └── documents.id = 394f5421-... (НОВЫЙ UUID)
         └── documents.deal_id → deals.id

deal_document_packages: document_id=394f5421..., deal_id=4e7082a1...
                                                    ← связь через documents, НЕ через document_intake
```

### Проблема: цепочка идентификации разорвана в двух местах

1. **`public.document_intake` → `deals.id`:** нет колонки promoted_deal_id
2. **`event.aggregate_id` (a2743303...) → `deals.id` (4e7082a1...):** разные UUID, нет табличной связи

Consumer'ы получают `event.aggregate_id = a2743303...` и не могут по нему найти сделку, потому что:
- DCR ищет `Deal.id == a2743303...` — не находит
- KR ищет `Document.id == a2743303...` — не находит (Document model маппится на `documents`, где UUID другие)
- Механизм, который знает о связи (accounting.document_intake.promoted_deal_id), НЕ используется consumer'ами

---

## 2. Sequence Analysis

### Реальная последовательность (as-is)

```
Phase 1: Upload → Pipeline
  document_intake.status = UPLOADED → VALIDATED → ACCEPTED → ANALYZED
  Код: backend/api/routes/processing.py

Phase 2: mark_document_ready (processing.py:118)
  document_intake.status = READY
  document.ready → outbox (event_outbox.aggregate_id = document_intake.document_id)
  ✅ Происходит синхронно в одном HTTP-запросе

Phase 3: EventPublisher polling loop
  Outbox → Publisher → Consumers (в background task uvicorn lifespan)
  ├── GraphSyncConsumer:      ✅ работает
  ├── DealContextResolutionConsumer: ⚠️ не находит сделку
  │   └── _find_deal_by_document: Deal.id == document_id → НЕ НАЙДЕН
  │   └── return — тихий выход без ошибки
  └── KnowledgeRuntimeConsumer:     ⚠️ не находит документ
      └── _load_document: Document.id == document_id → НЕ НАЙДЕН

Phase 4: UI/оператор вызывает promote_to_deal (ОТДЕЛЬНЫЙ HTTP-запрос)
  POST /documents/{document_id}/promote-to-deal
  ├── Создаёт deal: id = НОВЫЙ UUID
  ├── Создаёт document: id = НОВЫЙ UUID
  ├── Обновляет accounting.document_intake.promoted_deal_id
  └── ❌ НЕ обновляет public.document_intake
```

### Ожидаемая последовательность (как должно быть)

```
Phase 1: Upload → Pipeline → ANALYZED
Phase 2: promote_to_deal (должен происходить ДО document.ready)
  ├── Создаёт deal
  ├── Создаёт document
  ├── Обновляет public.document_intake.promoted_deal_id
  └── mark_document_ready (вызывается ПОСЛЕ promote_to_deal)
Phase 3: document.ready → Consumers
  ├── DCR: находит сделку через promoted_deal_id → разрешает контекст
  │   └── deal.accounting_ready → DealAccountingConsumer
  ├── KR: находит документ через document_intake
  └── ACC: создаёт AccountingDocument
```

### Последствия текущей последовательности

| Событие | Происходит когда | Consumer | Результат |
|---|---|---|---|
| `document.ready` | Сразу после pipeline | DCR | Deal not found → silent exit |
| `document.ready` | Сразу после pipeline | KR | Document not found → silent exit |
| `document.ready` | Сразу после pipeline | GSC | ✅ Работает (граф создаётся) |
| `deal.accounting_ready` | Никогда | ACC | Никогда не вызывается |
| `promote_to_deal` | ПОСЛЕ document.ready | — | Сделка создана, но события уже ушли |

---

## 3. Несоответствия (по приоритету)

### 3.1 [Blocker] DCR ID lookup — `Deal.id == document_id` не работает

**Файл:** `backend/infrastructure/consumers/deal_context_resolution_consumer.py`, строка 157

```python
stmt = select(Deal).where(Deal.id == document_id)
```

**Проблема:** `document_id` из события = `document_intake.document_id` (текстовый UUID) — НЕ равен `deals.id` (нативный UUID, генерируется в promote_to_deal).

**DB-доказательство:**
- `document_intake.document_id` = `a2743303-178a-40bf-bb07-3b380db2dc2d`
- `deals.id` = `4e7082a1-4f73-4d5b-94eb-2f6eb597c994`
- `consumer_processed_events`: `deal_context_resolution` = 1 запись
- DCR не создал ни одного `client` или `property`

**Чем должен быть заменён:**
- Proposal (раздел 3.1, строка 118): "Find the target Deal via `document_intake.promoted_deal_id`"
- Либо через `deal_document_packages`: `SELECT deal_id FROM deal_document_packages WHERE document_id IN (SELECT id FROM documents WHERE ...)`

### 3.2 [Blocker] KnowledgeRuntimeService читает из `documents`, данные в `document_intake`

**Файл:** `backend/services/knowledge_runtime/service.py`, строка 104-105

```python
result = await session.execute(
    select(Document).where(Document.id == document_id)
)
```

**Проблема:** `Document` SQLAlchemy модель маппится на таблицу `documents`. Pipeline пишет в `document_intake`. Эти таблицы:
- Имеют разные UUID для одного документа
- Не синхронизируются

**DB-доказательство:**
- `document_intake`: 1 запись (READY)
- `documents`: 3 записи с UUID, не совпадающими с `document_intake.document_id`
- `consumer_processed_events`: `knowledge_runtime` = 1 запись
- `graph_nodes` созданы, но **без profile** (только title: "document")

### 3.3 [Blocker] `deal.accounting_ready` никогда не эмитится

**Файл:** `backend/infrastructure/consumers/deal_context_resolution_consumer.py`, строка 136

```python
await self._emit_accounting_ready(deal, event)  # строка 136
```

**Проблема:** `_emit_accounting_ready()` вызывается на строке 136 ТОЛЬКО после успешного `resolver.apply()`. До этого на строке 96 — `return` (deal not found). Даже если DCR найдёт сделку:
- `deal.price = 0.00`, `deal.commission = 0.00`, `deal.deposit_amount = 0.00`
- Будут переданы нулевые значения

**DB-доказательство:**
- `event_outbox`: только `document.ready` — нет `deal.accounting_ready`
- `consumer_processed_events`: нет записей `deal_accounting`
- Таблица `accounting_documents` не существует

### 3.4 [High] Отсутствует `promoted_deal_id` в `public.document_intake`

**Файл:** `backend/api/routes/promote_to_deal.py`, строка 238

```python
await conn.execute(
    "UPDATE accounting.document_intake SET promoted_deal_id=$1 ..."
)
```

**Проблема:** Обновляется только `accounting.document_intake` (другая схема). `public.document_intake` не получает `promoted_deal_id`.

**DB-доказательство:**
- `public.document_intake` — нет колонки `promoted_deal_id`
- `accounting.document_intake` — есть `promoted_deal_id`

Consumer'ы работают с `public` схемой через SQLAlchemy и не имеют доступа к accounting схеме.

### 3.5 [High] Нулевые финансовые поля на сделке

**Файл:** `backend/api/routes/promote_to_deal.py`, строки 212, 231-233

```python
price = 0.0  # строка 212 — дефолт, даже если amounts есть
# ...
INSERT INTO public.deals (... commission, deposit_amount ...)
VALUES (..., 0.0, 0.0)  # строки 229-235
```

**DB-доказательство:**
- `deal.price = 0.00`
- `deal.commission = 0.00`
- `deal.deposit_amount = 0.00`

Даже при исправлении sequence, `_emit_accounting_ready()` отправит нулевые значения.

### 3.6 [High] Отсутствуют таблицы `embeddings` и `accounting_documents`

**DB-доказательство:**
- `embeddings`: ❌ не существует
- `accounting_documents`: ❌ не существует

Блокирует:
- KnowledgeRuntime embedding pipeline
- DealAccountingConsumer создание AccountingDocument

### 3.7 [Medium] Sequence: `document.ready` до promote_to_deal

Событие эмитится сразу после pipeline, а сделка создаётся позже. Ни Freeze Record, ни Proposal не предписывают изменить sequence, но это фундаментальная причина всех блокеров.

---

## 4. Root Cause Analysis

### Коренная причина

```
Все три блокера (DCR, KR, ACC) сводятся к одной проблеме:

    ОТСУТСТВИЕ МОСТА МЕЖДУ Epic 1 (Document Intake) и Epic 3 (Deal/Document)

document_intake (Epic 1)          documents + deals (Epic 3)
┌────────────────────────┐       ┌────────────────────────┐
│ document_id: a27433…   │       │ id: 394f5421…         │
│ checksum: 58f779…      │       │ deal_id: 4e7082a1…    │
│ status: READY          │       │                        │
│ profile: {полные       │       │ deals:                 │
│   данные из OCR}       │       │   id: 4e7082a1…       │
│                        │       │   price: 0.0           │
│                        │       │   commission: 0.0      │
│                        │       │   deposit: 0.0         │
│ ❌ promoted_deal_id    │       │                        │
└────────────────────────┘       └────────────────────────┘
         │                               │
         │    НЕТ СВЯЗИ                   │
         └───────────────────────────────┘
```

### Каскад последствий

```
document.ready (aggregate_id = a27433...)
  │
  ├── DCR: _find_deal_by_document(document_id = a27433...)
  │     └── select(Deal).where(Deal.id == a27433...)
  │           └── ❌ NOT FOUND
  │                 └── return (silent exit)
  │                       └── НЕ вызывается _emit_accounting_ready()
  │                             └── deal.accounting_ready NOT emitted
  │                                   └── DealAccountingConsumer NEVER fires
  │
  └── KR: _load_document(document_id = a27433...)
        └── select(Document).where(Document.id == a27433...)
              └── ❌ NOT FOUND
                    └── return (silent exit)
                          └── НЕ создаются chunks/embeddings/graph_node
```

### Почему это произошло

1. **Freeze Record не специфицирует механизм привязки сделки к документу.** Он фиксирует, что DCR обрабатывает `document.ready` и находит сделку, но не специфицирует **как** consumer должен найти сделку по `document_id`.

2. **DCR Proposal правильный, но реализация отличается.** Proposal говорит: "Find the target Deal via document_intake.promoted_deal_id". Реализация использует `Deal.id == document_id` — это нерабочий shortcut.

3. **Promote_to_deal создаёт новые UUID без привязки к Event ID.** `event.aggregate_id` не совпадает ни с `deals.id`, ни с `documents.id`. Нет обратного пути от события к сделке.

4. **Dual document tables — архитектурный дефект слияния Epic 1 и Epic 3.** Epic 1 использует `document_intake` с сырыми данными. Epic 3 вводит новую таблицу `documents` с моделью `Document`. Данные не мигрированы, синхронизация отсутствует.

---

## 5. Proposal — минимальные исправления

### 🔴 Fix 1: DCR ID lookup — искать через правильный механизм

**Файл:** `backend/infrastructure/consumers/deal_context_resolution_consumer.py`, строка 141-165

**Замена `_find_deal_by_document()`:**

```python
async def _find_deal_by_document(
    self,
    session,
    document_id: UUID,
) -> Deal | None:
    # 1. Сначала — поиск по promoted_deal_id в document_intake
    #    (после исправления Fix 3, колонка promoted_deal_id будет добавлена)
    from sqlalchemy import text
    result = await session.execute(
        text("SELECT promoted_deal_id FROM document_intake WHERE document_id = :doc_id"),
        {"doc_id": str(document_id)}
    )
    row = result.fetchone()
    if row and row[0]:
        deal_id = UUID(str(row[0]))
        deal = await session.get(Deal, deal_id)
        if deal:
            return deal
    
    # 2. Fallback — поиск через deal_document_packages
    #    Если promote_to_deal создал documents запись с file_hash,
    #    то можно найти deal через цепочку document_intake.checksum → documents.file_hash
    #    → deal_document_packages.deal_id
    #    НО: documents не хранит file_hash из document_intake (нужно добавить)
    
    return None  # deal not found — не retryable
```

**Затрагивает:** Только DCR consumer.

---

### 🔴 Fix 2: KnowledgeRuntimeService — читать из document_intake

**Файл:** `backend/services/knowledge_runtime/service.py`, строка 98-107

**Замена `_load_document()`:**

```python
async def _load_document(
    self,
    session: AsyncSession,
    document_id: UUID,
) -> Document | None:
    """Load a document by ID — reads from document_intake via raw SQL.
    
    Uses document_intake as source of truth (Epic 1 pipeline writes here).
    Falls back to documents table for backward compatibility.
    """
    from sqlalchemy import text as sa_text
    
    # Primary: read from document_intake (Epic 1 source of truth)
    row = await session.execute(
        sa_text("""
            SELECT document_id, original_filename, checksum, profile, status
            FROM document_intake WHERE document_id = :doc_id
        """),
        {"doc_id": str(document_id)}
    )
    doc_row = row.fetchone()
    if doc_row:
        # Create/update Document model instance from document_intake data
        from backend.models.document import Document
        from datetime import datetime, timezone
        doc = Document(
            id=UUID(str(doc_row[0])),
            title=doc_row[1] or "document",
            # ... map fields
        )
        return doc
    
    # Fallback: original lookup in documents table
    result = await session.execute(
        select(Document).where(Document.id == document_id)
    )
    return result.scalar_one_or_none()
```

**Альтернатива:** Создать sync механизм: при `mark_document_ready()` создавать/обновлять запись в `documents`. Но это дублирование данных.

**Затрагивает:** KnowledgeRuntimeService.

---

### 🔴 Fix 3: Добавить `promoted_deal_id` в `public.document_intake`

**Файл:** `backend/api/routes/promote_to_deal.py`, строка 238

**Изменение:** После обновления `accounting.document_intake`, добавить обновление `public.document_intake`:

```python
# Mark promoted (accounting schema — existing)
await conn.execute(
    "UPDATE accounting.document_intake SET promoted_deal_id=$1, confidence_auto_promoted=$2 WHERE id=$3",
    deal_id, conf_level == ConfidenceLevel.AUTO_PROMOTE, document_id
)

# Mark promoted (public schema — NEW)
await conn.execute(
    "UPDATE public.document_intake SET promoted_deal_id=$1 WHERE document_id=$2",
    deal_id, document_id
)
```

**Также нужна миграция:** Добавить колонку `promoted_deal_id text` в `public.document_intake`.

**Затрагивает:** promote_to_deal route + DDL migration.

---

### 🟡 Fix 4: Заполнять финансовые поля из профиля документа

**Файл:** `backend/api/routes/promote_to_deal.py`, строка 212-215

**Изменение:** Заполнять `price`, `commission`, `deposit_amount` из extracted_fields при создании сделки:

```python
# Извлечь финансовые данные из extracted_fields
price = 0.0
commission = 0.0
deposit_amount = 0.0

if fields.get("amounts"):
    try:
        price = max(float(a) for a in fields["amounts"])
    except (ValueError, TypeError):
        pass

# Дополнительно: проверить financial_terms из profile
if isinstance(fields, dict):
    financial_terms = fields.get("financial_terms", {})
    if financial_terms:
        total_price = financial_terms.get("total_price", {})
        if isinstance(total_price, dict) and "value" in total_price:
            try:
                price = max(price, float(total_price["value"]))
            except (ValueError, TypeError):
                pass
        commission = financial_terms.get("commission", 0.0)
        deposit_amount = financial_terms.get("deposit_amount", 0.0)
```

**Затрагивает:** promote_to_deal route.

---

### 🟡 Fix 5: Создать недостающие таблицы

**Требуется DDL:**

```sql
-- embeddings table (KR ADR-004)
CREATE TABLE IF NOT EXISTS public.embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES public.document_intake(document_id),
    chunk_id UUID NOT NULL,
    model VARCHAR(50) NOT NULL,
    vector vector(768),       -- pgvector
    content_hash VARCHAR(64) UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- accounting_documents table (ACC ADR-003/004/005)
CREATE TABLE IF NOT EXISTS public.accounting_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deal_id UUID NOT NULL REFERENCES public.deals(id),
    source_event_id UUID NOT NULL,
    source_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'READY',
    document_type VARCHAR(50) NOT NULL,
    amount NUMERIC(15,2) NOT NULL DEFAULT 0,
    currency VARCHAR(3) NOT NULL DEFAULT 'RUB',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**Затрагивает:** DDL только — код consumer'ов уже написан.

---

### 🟢 Fix 6: Sequence — задержать document.ready (опционально, требует ADR)

**Варианты решения (требует нового ADR, т.к. затрагивает архитектуру Freeze Record):**

1. **Отложить document.ready до promote_to_deal:**
   - Pipeline завершается → статус ANALYZED
   - `mark_document_ready()` вызывается в promote_to_deal ПОСЛЕ создания сделки
   - document.ready эмитится когда сделка уже существует

2. **Событие deal.document_attached:**
   - document.ready остаётся как есть (для GraphSyncConsumer и KnowledgeRuntimeConsumer)
   - promote_to_deal эмитит `deal.document_attached`
   - DCR consumer переключается на `deal.document_attached`

3. **Deferred DCR:** DCR consumer принимает, что сделки может не быть, и сохраняет событие для повторной обработки после promote_to_deal.

**Рекомендация:** Вариант 1 — **эмитить document.ready после promote_to_deal**. Это минимальное изменение sequence без введения новых событий. Требует ADR.

---

## 6. File Manifest

| Файл | Изменение | Приоритет |
|---|---|---|
| `backend/infrastructure/consumers/deal_context_resolution_consumer.py` | Fix 1: ID lookup | 🔴 |
| `backend/services/knowledge_runtime/service.py` | Fix 2: источник данных | 🔴 |
| `backend/api/routes/promote_to_deal.py` | Fix 3: promoted_deal_id | 🔴 |
| `backend/api/routes/promote_to_deal.py` | Fix 4: financial fields | 🟡 |
| `migrations/XXX_add_promoted_deal_id.sql` | Fix 3: DDL колонки | 🔴 |
| `migrations/YYY_create_embeddings.sql` | Fix 5: DDL embeddings | 🟡 |
| `migrations/ZZZ_create_accounting_documents.sql` | Fix 5: DDL accounting_documents | 🟡 |
| `backend/services/document_lifecycle.py` | Fix 6 (ADR): sequence change | 🟢 |

---

## 7. ADR Impact

| Изменение | Нужен ли ADR | Почему |
|---|---|---|
| Fix 1 (DCR ID lookup) | ❌ Нет | Implementation detail — функциональность не меняется, только корректируется lookup |
| Fix 2 (KR source) | ❌ Нет | Implementation detail — источник данных меняется, но интерфейс не меняется |
| Fix 3 (promoted_deal_id) | ❌ Нет | Schema change в рамках существующей колонки |
| Fix 4 (financial fields) | ❌ Нет | Data quality — не архитектурное изменение |
| Fix 5 (DDL) | ❌ Нет | Missing tables — планировались по ADR, не были созданы |
| Fix 6 (sequence) | ✅ **Да** | Изменяет lifecycle — когда эмитится document.ready. Требует ADR на изменение Freeze Record |

### Необходимые изменения в Freeze Record (для Fix 6):

```diff
- Документ: Pipeline → READY → document.ready → Consumers
+ Документ: Pipeline → ANALYZED → promote_to_deal → READY → document.ready → Consumers
```

---

## 8. Acceptance Criteria

### После исправлений (Fix 1-4):

```
Upload → Pipeline → ANALYZED → promote_to_deal → READY → document.ready
  │
  ├── GraphSyncConsumer: ✅ graph_nodes = 1 (Document + profile)
  │
  ├── DealContextResolutionConsumer:
  │   ├── _find_deal_by_document: находит deal через promoted_deal_id ✅
  │   ├── Resolves Property (cadastral/address) → property_id на сделке ✅
  │   ├── Resolves Clients (INN/name) → DealParticipant rows ✅
  │   ├── Logs resolution_attempt (RESOLVED/AMBIGUOUS/NOT_FOUND) ✅
  │   ├── Emits deal.updated ✅
  │   └── Emits deal.accounting_ready ✅
  │
  ├── KnowledgeRuntimeConsumer:
  │   ├── Загружает документ из document_intake ✅
  │   ├── Создаёт graph_node с profile/metadata ✅
  │   └── Создаёт chunks → embeddings (после Fix 5) ✅
  │
  └── DealAccountingConsumer (на deal.accounting_ready):
      ├── Создаёт AccountingDocument (commission + deposit) ✅
      └── Status = READY ✅
```

### Проверка в БД

| Consumer | SQL проверка | Ожидание |
|---|---|---|
| DCR | `SELECT * FROM consumer_processed_events WHERE consumer_name = 'deal_context_resolution'` | count >= 1 |
| DCR | `SELECT * FROM clients` / `SELECT * FROM properties` | Есть записи |
| DCR | `SELECT promoted_deal_id FROM document_intake WHERE document_id = '...'` | NOT NULL |
| DCR | `SELECT deal.accounting_ready FROM event_outbox` | 1 запись |
| KR | `SELECT * FROM graph_nodes WHERE source_entity_type = 'document'` | Есть запись с profile |
| ACC | `SELECT * FROM accounting_documents WHERE deal_id = '...'` | ≥ 1 запись |

---

## 9. Implementation Plan

### Step 1 — DDL миграции (Fix 3 + Fix 5)

```sql
-- 1. Добавить promoted_deal_id в public.document_intake
ALTER TABLE public.document_intake ADD COLUMN promoted_deal_id text;

-- 2. Создать embeddings (если pgvector установлен)
CREATE TABLE IF NOT EXISTS public.embeddings (...);

-- 3. Создать accounting_documents
CREATE TABLE IF NOT EXISTS public.accounting_documents (...);
```

**Проверка:** `SELECT promoted_deal_id FROM document_intake LIMIT 1` — колонка существует.

---

### Step 2 — promote_to_deal (Fix 3 + Fix 4)

**Файл:** `backend/api/routes/promote_to_deal.py`

1. После строки 239 добавить обновление `public.document_intake.promoted_deal_id`
2. Исправить извлечение `price`, `commission`, `deposit_amount` из `extracted_fields` (строки 212-215)

**Проверка:** После promote_to_deal, `document_intake.promoted_deal_id` заполнен.

---

### Step 3 — DCR consumer (Fix 1)

**Файл:** `backend/infrastructure/consumers/deal_context_resolution_consumer.py`

1. Заменить `_find_deal_by_document()` на поиск через `document_intake.promoted_deal_id`

**Проверка:** DCR находит сделку → clients/properties созданы → deal обновлён.

---

### Step 4 — KnowledgeRuntimeService (Fix 2)

**Файл:** `backend/services/knowledge_runtime/service.py`

1. Изменить `_load_document()` на чтение из `document_intake`

**Проверка:** KR создаёт graph_node с profile.

---

### Step 5 — Regression тесты

1. Загрузить документ → pipeline → READY
2. Вызвать promote_to_deal
3. Проверить consumer_processed_events (все 4 consumer'а + DCR создал clients/properties)
4. Проверить event_outbox (deal.accounting_ready)
5. Проверить accounting_documents

---

## 10. Заключение

### Оценка текущего состояния: ⚠️ PARTIAL — Backbone работает, Product Layer разрывает связи

**Что работает:**
- Event Backbone (Outbox, Publisher, Consumer Framework) — ✅ 100%
- GraphSyncConsumer — ✅ создаёт graph_nodes
- Consumer регистрация — ✅ все 4 consumer'а зарегистрированы
- DCR код разрешения контекста — ✅ корректен, проблема в ID lookup
- KR код embedding pipeline — ✅ корректен, проблема в источнике данных
- ACC код создания AccountingDocument — ✅ корректен, проблема в отсутствии события

**Что не работает (все три блокера — одна коренная причина):**
- DCR не находит сделку → всё остальное не работает
- KR не находит документ → chunks/embeddings не созданы
- `deal.accounting_ready` не эмитится → DealAccountingConsumer не срабатывает

### Root Cause

**Разрыв идентификации между Epic 1 (`document_intake`) и Epic 3 (`deals`, `documents`).**

Три проявления одной проблемы:

| Симптом | Причина | Fix |
|---|---|---|
| DCR: `Deal.id != document_id` | Нет promoted_deal_id в public.document_intake | Fix 1 + Fix 3 |
| KR: читает из пустой `documents` | Данные в `document_intake`, модель читает `documents` | Fix 2 |
| ACC: не срабатывает | `_emit_accounting_ready()` не вызывается из-за DCR failure | Fix 1 (каскадно) |

### Минимальные изменения для рабочего E2E (4 файла)

1. **DCR consumer** — ID lookup через `document_intake.promoted_deal_id`
2. **KR service** — источник данных: `document_intake` вместо `documents`
3. **promote_to_deal route** — обновлять `public.document_intake.promoted_deal_id`
4. **promote_to_deal route** — заполнять price из extracted_fields

+ DDL миграции (promoted_deal_id, embeddings, accounting_documents)

### Что НЕ требует изменений

- Event Backbone — ✅
- BaseConsumer / ConsumerStateRepository — ✅
- GraphSyncConsumer — ✅
- Регистрация consumer'ов в `main.py` — ✅
- DCR resolver (CandidateFinder, DealContextResolver) — ✅
- KnowledgeRuntimeService pipeline — ✅
- DealAccountingConsumer — ✅
- DealApplicationService — ✅

---

*Конец отчёта. Architecture Review — Epic 3 Product Layer Alignment.*
