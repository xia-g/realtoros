# Stream E — Document Profile Consumers (Architecture Invariant)

```
Epic              1 — Intelligent Document Intake
Stream            E — Document Profile Consumers
Status            Architecture Audit + Contract Definition
Predecessor       Stream D.1 — Integration Fixes (MILESTONE: Profile is Canonical)
Code changes      0
```

──────────────────────────────────────────────────────
## E1 — Consumer Audit

| Consumer | Source | OCR? | Legacy fields? | Document.profile? | Status |
|:---------|:-------|:----:|:--------------:|:-----------------:|:------:|
| **Deal** | `deals.py` | ❌ | fallback | ✅ sections.parties.buyer.name | **PASS** |
|          |           |     |           | ✅ sections.financial_terms.total_price |         |
| **Routing** | `routing.py` | ❌ | ❌ | ✅ engine.evaluate(doc.profile) | **PASS** |
| **Knowledge** | pipeline → knowledge_step | ❌ | ❌ | source_document_id (link only) | **PASS** |
| **Accounting** | `accounting.py:389` | ❌ | ⚠️ `fields` dict | ✅ `profile.get("fields")` | **LEGACY** |
| **Search** | `event_handlers.py:49` | — | — | — | **NOT IMPLEMENTED** (stub) |
| **AI / Embedding** | `event_handlers.py:40` | — | — | — | **NOT IMPLEMENTED** (stub) |
| **Frontend** | `page.tsx:163-183` | ❌ | ⚠️ `fields.supplier` | ✅ `profile.document_type` | **LEGACY** |

### PASS (используют Document.profile)

- **Deal** — читает `sections.parties.buyer.name`, `sections.financial_terms.total_price`
- **Routing** — передаёт весь `doc.profile` в `engine.evaluate()`
- **Knowledge** — собственная immutable модель, связь через `source_document_id`

### LEGACY (используют legacy fields внутри profile)

- **Accounting** — читает `profile.fields` (старый плоский dict)
- **Frontend** — читает `profile.fields.supplier` для отображения

Оба получают данные через `Document.profile`, но обращаются к legacy `fields`, а не к новым `sections`. Это не нарушает инвариант "не читать OCR", но снижает качество данных.

### NOT IMPLEMENTED

- **Search** — `search_index_handler` (event_handlers.py:49) — **заглушка**. Реальный `KnowledgeSearchService` читает `DocumentChunk.content` (сырой OCR), что нарушает инвариант. Будущая реализация должна строить поисковый индекс из `Document.profile.sections`.
- **AI / Embedding** — `embedding_sync_handler` (event_handlers.py:40) — **заглушка**. `EmbeddingPipeline` читает сырой `raw_text`. Будущая реализация должна эмбеддить секции профиля, а не сырой OCR.

Будущие реализации обязаны использовать `Document.profile` как единственный источник.

──────────────────────────────────────────────────────
## E2 — Document.profile Contract Definition

### Document.profile — единственный публичный API Document Layer

**Преамбула.**  
Document.profile — это каноническая структурированная модель документа.  
Она создаётся один раз, после завершения Processing Pipeline, и сохраняется в `document_intake.profile` (JSONB).

Любой Product Consumer получает структурированные данные документа **только** через Document.profile.  
Чтение OCR напрямую запрещено.  
Чтение промежуточных результатов pipeline запрещено.

**Структура.**

```json
{
  "profile_version": "1.0",
  "document_type": "contract | invoice | act | ...",
  "confidence": 0.885,
  "sections": {
    "identification":    { "contract_number": "...", "contract_date": "...", ... },
    "parties":           { "seller": { "name", "inn", ... }, "buyer": { ... } },
    "financial_terms":  { "total_price": { "value", "currency" }, ... },
    "property":         { "address", "cadastral_number", ... },
    "dates":            { "signing_date", ... },
    "references":       { "tender_number", ... }
  },
  "fields": { /* legacy — плоский dict */ },
  "metadata": { "extracted_by", "confidence_per_field", "warnings" }
}
```

**Правила.**

1. `sections` — основной источник. Всегда предпочтителен.
2. `fields` — legacy compatibility. Сохраняется, но не расширяется.
3. `metadata` — служебная информация (confidence, warnings).
4. Секции могут отсутствовать для типов документов, где они не применимы.

**Обязанность потребителя.**

- Читать `profile.sections.<section>.<field>`.
- При отсутствии секции — использовать fallback (null / значение по умолчанию).
- НЕ читать OCR напрямую.

### Допустимые источники данных

```
✅ profile.sections.identification.contract_number
✅ profile.sections.parties.buyer.name
✅ profile.sections.financial_terms.total_price.value
✅ profile.metadata.warnings
⚠️ profile.fields.supplier          (legacy — не расширять)
❌ ocr_step.result.raw_text         (internal — не использовать)
❌ extraction_step.result.protobuf  (internal — не существует)
```

──────────────────────────────────────
## E3 — Migration Matrix

| Источник | Статус | Описание | План |
|:---------|:------:|:---------|:-----|
| **OCR raw_text** | 🔒 Internal | Временные данные pipeline. Хранится в `processing_steps.result.ocr.raw_text`. | Не публиковать. Не удалять (нужен для отладки). |
| **Extraction internals** | 🔒 Internal | Результаты отдельных extractor'ов. | Не публиковать. |
| **fields** (legacy dict) | ⚠️ Legacy | Плоский dict с v1 полями. Сохраняется для обратной совместимости. | Заморозить. Не добавлять новые поля. Удалить через N версий. |
| **profile.sections** | ✅ Canonical | Структурированная модель документа. | Единственный источник. Расширять при необходимости. |
| **profile.metadata** | ✅ Canonical | Служебные данные (confidence, warnings). | Читать при необходимости. |

### Timeline

```
v1.x (сейчас)     fields + sections сосуществуют
v2.0              fields удалён, только sections
                  обязательство: все consumer'ы переведены на sections
```

──────────────────────────────────────
## E4 — Architecture Invariant (Product Consumer Invariant)

### Формулировка

> Ни один компонент Product Layer не читает OCR напрямую.
>
> Ни один компонент Product Layer не зависит от реализации Extraction Pipeline.
>
> Единственным источником структурированных данных документа является **Document.profile**.

### Обоснование

1. **Производительность.**  
   Не нужно перечитывать OCR и перезапускать extraction для каждого потребителя.

2. **Согласованность.**  
   Все потребители видят одни и те же данные. Нет расхождений между Deal, Accounting, и AI.

3. **Изоляция.**  
   Pipeline можно переписать, заменить OCR-движок, добавить AI-извлечение —  
   потребители этого не заметят. Они читают profile.

4. **Тестируемость.**  
   Любой consumer можно тестировать с синтетическим profile, без реального OCR.

5. **Эволюция.**  
   Profile можно расширять новыми секциями, не меняя потребителей.

### Нарушение инварианта считается

**архитектурной ошибкой.**

Любой код, который читает `processing_steps` напрямую из продукта,  
или обращается к сырому OCR-тексту,  
должен быть отклонён на code review.

### Исключения

- **Knowledge Layer** — имеет собственную immutable модель (`KnowledgeRevision`),  
  но получает данные из pipeline, а не читает profile напрямую.  
  Связь: `knowledge_revision.source_document_id → document.document_id`.  
  Это не нарушение, это разделение ответственности.

- **Pipeline internals** — внутри pipeline (extraction step) можно читать OCR raw_text,  
  потому что extraction создаёт profile.  
  Это **внутренняя** операция, невидимая для потребителей.

──────────────────────────────────────
## Architecture Diagram (после Stream E)

```
                Document Layer

                    Document
                       │
                       ▼
               Document.profile
                       │
    ┌──────────┬──────────┬──────────┬──────────┬──────────┐
    ▼          ▼          ▼          ▼          ▼          ▼
   Deal     Routing   Accounting    AI       Search   (Contract)
   
       ── Все через profile ──
       Никто не читает OCR
```

──────────────────────────────────────
## Файлы с инвариантом

- `docs/architecture/product-consumer-invariant.md` — настоящий документ
- `backend/api/deals.py` — пример корректного consumer'а ✅
- `backend/api/routes/routing.py` — пример корректного consumer'а ✅
- `backend/api/routes/accounting.py` — legacy compat, требует миграции ⚠️
- `frontend/app/imports/documents/page.tsx` — legacy compat, требует миграции ⚠️
- `backend/core/event_handlers.py` — stub для Search/AI, будущие реализации должны читать profile ⏳

──────────────────────────────────────
## GO / NO-GO

**GO.** Инвариант принят.  
**GO.** Contract зафиксирован.  
**GO.** Legacy поля заморожены.  
**GO.** Новые consumer'ы обязаны читать profile.

Ноль изменений кода.  
Ноль Platform changes.  
Ноль Knowledge changes.  
Один ADR.  
Один инвариант.
