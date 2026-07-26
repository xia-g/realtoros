# Knowledge Search v1 — Capability Proposal

```
Status            PROPOSED (Phase 0)
Capability        Knowledge Search v1
──────────────────────────────────────────────
Architecture      v2.3.1
Baseline
──────────────────────────────────────────────
Cycle             2 (writing — после Diff)
──────────────────────────────────────────────
Date              2026-07-21
```

## 1. Search Intent

### Primary (v1): Level 1 — KnowledgeRevision Search

"Find KnowledgeRevision objects deterministically using
existing domain metadata."

Пользовательские вопросы, на которые отвечает v1:

- "Покажи все изменения по сделке"
- "Найди ревизии, связанные с документом X"
- "Какие знания были созданы вчера?"
- "Какие изменения внесены конкретным источником?"
- "Покажи последние revision для entity"

### Secondary (v1.1): Level 2 — Knowledge Node Search

Поиск по semantic entities в проекциях.
Не входит в v1.

### Deferred: Level 3 — Full-text Knowledge Search

Поиск по естественному языку, индексация, ранжирование.
Не входит в v1.

## 2. Search Scope

Primary search fields (Level 1):

| Поле | Тип | Источник | Поиск | Фильтр |
|------|:---:|:---------|:-----:|:------:|
| `revision_id` | TEXT PK | `knowledge_revisions` | exact | ❌ |
| `source_document_id` | TEXT | `knowledge_revisions` | exact / prefix | ✅ |
| `created_at` | TIMESTAMP | `knowledge_revisions` | range | ✅ |
| `reason` | TEXT (из JSONB metadata) | `knowledge_revisions.metadata->>reason` | substring / ILIKE | ✅ |
| `created_by` | TEXT (из JSONB metadata) | `knowledge_revisions.metadata->>created_by` | exact | ✅ |
| `revision_number` | INTEGER | `knowledge_revisions` | exact / range | ✅ |

Сортировка:
- `created_at ASC / DESC`
- `revision_number ASC / DESC`

Поведение:
- детерминированная сортировка: `ORDER BY created_at DESC, revision_id ASC`
- пагинация курсорная (аналогично Timeline)

## 3. Source of Truth

```
Option A: PostgreSQL напрямую (рекомендован для v1)
─────────────────────────────────────────────────────
Преимущества:
- полный контроль над SQL
- pg_trgm для fuzzy / ILIKE
- JSONB operators для metadata
- индексы уже существуют
- 0 изменений Platform

Недостатки:
- прямое подключение в route (как Explorer / Timeline)
- Schema change = migration (не требуется для v1)

Архитектурное влияние:
- Platform files changed = 0
- ADR required = No
```

Другие варианты (отклонены для v1):

```
Option B: Projection layer
─ не оптимизирован для поиска (key-value store)
─ поиск по JSONB через ProjectionStore = N + 1

Option C: Search abstraction
─ premature — нужен после измерения объёмов

Option D: Отдельный индекс (Elastic / Meilisearch)
─ premature — не знаем объёмов
─ будет ADR, когда потребуется
```

## 4. Platform Boundary Analysis

### Invariant: Platform files changed = 0

| Компонент | Изменяется? | Обоснование |
|-----------|:-----------:|-------------|
| Domain | ❌ | не затрагивается |
| KnowledgeRevision | ❌ | не затрагивается |
| KnowledgeSnapshot | ❌ | не затрагивается |
| Projection DTO | ❌ | не затрагивается |
| Repository Protocol | ❌ | не затрагивается |
| ProjectionStore | ❌ | не затрагивается |
| Materialization | ❌ | не затрагивается |
| Query DSL / Engine | ❌ | не затрагивается |
| Bootstrap | ❌ | не затрагивается |

Search — чистое чтение. Те же механизмы, что в Explorer / Timeline.

**Если потребуется изменить Platform:**
- зафиксировать ADR
- Architecture Review
- Backlog

**Прогноз:** Search v1 (Level 1) укладывается в Capability без изменения Platform.

## 5. Query Model (предварительная)

```python
@dataclass(frozen=True)
class SearchFilter:
    source_document_id: str | None = None
    reason_contains: str | None = None       # ILIKE
    created_by: str | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None
    revision_number_min: int | None = None
    revision_number_max: int | None = None

@dataclass(frozen=True)
class SearchSort:
    field: str = "created_at"                 # created_at | revision_number
    direction: str = "DESC"                   # ASC | DESC

@dataclass(frozen=True)
class SearchQuery:
    filters: SearchFilter = field(default_factory=SearchFilter)
    sort: SearchSort = field(default_factory=SearchSort)
    cursor: str | None = None
    limit: int = 20

@dataclass(frozen=True)
class SearchResult:
    revision_id: str
    revision_number: int
    source_document_id: str
    created_at: str
    reason: str
    created_by: str
```

Ранжирование: для v1 **не требуется**.
Результаты сортируются по `created_at DESC` + `revision_id ASC`.

## 6. Index Question

```
Нужен ли индекс для v1?
────────────────────────────────────────────
Ответ: существующих индексов достаточно.

Существующие индексы на knowledge_revisions:
- PK on revision_id
- idx_kr_created_at
- idx_kr_source_doc (на source_document_id)

Планируемые (в рамках API route, не Platform):
- GIN или pg_trgm на metadata (ILIKE search по reason)
  └ добавляется как миграция БД, не Platform file

Когда понадобится новый индекс:
- после измерения объёмов (> 10k revisions)
- при появлении Level 2 (Node поиск)
- при добавлении full-text
```

Не делать оптимизацию заранее.

## 7. Capability Boundary

```
Responsibility: Knowledge Search Capability
────────────────────────────────────────────
✓ Определение SearchQuery / SearchFilter
✓ Выполнение поиска через прямой SQL (Option A)
✓ Формирование SearchResult
✓ Пагинация
✓ Детерминированная сортировка
✓ API endpoint

NOT Responsibility:
────────────────────────────────────────────
✗ Изменение Domain model
✗ Изменение Repository
✗ Изменение Projection
✗ Семантический поиск (Level 2+ deferred)
✗ Ранжирование (v1)
✗ Full-text indexing
✗ Инфраструктурные миграции (Platform)
```

## 8. Validation Plan

### Acceptance Criteria (v1)

```
□ Platform files changed = 0
□ ADR required = No
□ Architecture Review = No
□ Existing regressions = PASS
□ Search returns deterministic results
□ Stable ordering (created_at DESC, revision_id ASC)
□ Cursor pagination deterministic
□ Filter by source_document_id
□ Filter by date range
□ Filter by reason (ILIKE)
□ Explorer compatibility preserved
□ Timeline compatibility preserved
□ Diff Explorer compatibility preserved
□ Covered by tests
```

### Invariants

```
Search(A, same filters) → same pagination
Search(empty results)   → [] + cursor: null
Search filters are AND  → additive, not exclusive
```

### GO / NO-GO Decision

После подтверждения Phase 0:

```
Baseline compatibility:    ?
Platform changes:          ?
ADR:                       ?
Implementation:            ?
```

## 9. Architectural Objective

Knowledge Search v1 validates that the Platform supports
deterministic query operations over existing domain data
without modifying Domain, Persistence, or Projection models.

The purpose of v1 is to validate search capability boundaries,
not to solve semantic discovery. Search completes the natural
first cycle of Capability operations:

```
Explorer     — locate a single state
Timeline     — navigate through history
Diff         — compare two states
Search       — find knowledge by criteria
```

## 10. Included / Excluded (v1)

```
Included:
────────────────────────────
✓ Revision metadata search
✓ Date range filtering
✓ Document reference filtering
✓ Entity reference filtering (by existing IDs)
✓ Stable ordering
✓ Cursor pagination
✓ Deterministic results

Excluded:
────────────────────────────
✗ JSONB semantic attribute search (Level 2)
✗ Full-text search (Level 3)
✗ Ranking / relevance scoring
✗ Fuzzy matching
✗ Natural language queries
✗ Node-level search
```
