# Knowledge Audit Trail v1 — Capability Proposal

```
Status            PROPOSED (Phase 0)
Capability        Knowledge Audit Trail v1
──────────────────────────────────────────────
Architecture      v2.5
Baseline
──────────────────────────────────────────────
Cycle             4 (Knowledge Trust & Recovery)
──────────────────────────────────────────────
Date              2026-07-21
```

## 1. Audit Intent

Что именно должен объяснять Audit Trail?

**Primary intent v1:**
Показать полную историю происхождения, изменений и проверок
для заданного KnowledgeRevision или Entity.

Пользовательский сценарий:

```
Пользователь видит KnowledgeRevision
    ↓
"Откуда это знание?"
    ↓
Audit Trail показывает:
    ├── revision_id, created_at, created_by, reason
    ├── source_document_id
    ├── provenance chain (какие документы использованы)
    ├── consistency check result (были ли нарушения)
    └── ссылки на соседние revision (previous / next)
```

**Deferred (not v1):**
- Trust score / confidence level
- Semantic conflict history
- Approval workflow
- User action log (кто что менял)

## 2. Audit Scope

### Revision history (v1)

```
✓ Revision chain (previous / next by time)
✓ Created_at, created_by, reason
✓ Source document reference
✓ Revision number progression
```

### Validation history (v1)

```
✓ Consistency Check result (computed on demand)
✓ Violations found (if any)
✓ Check timestamp
```

### Trust history (deferred)

```
✗ Trust score evolution
✗ Confidence level
✗ Approval state
✗ User reputation
```

## 3. Source of Truth

### Option A: Existing KnowledgeRevision history (recommended for v1)

```
Преимущества:
- PostgreSQL knowledge_revisions таблица уже содержит:
  revision_id, revision_number, source_document_id, created_at, metadata
- KnowledgeRevisionRepository уже предоставляет get() и get_by_document_id()
- 0 изменений Platform

Недостатки:
- Не хранит результаты Consistency Check (нужно пересчитывать)
- Не хранит "кто выполнял проверку"
```

### Option B: KnowledgeSnapshot metadata

```
KnowledgeSnapshot содержит provenance и explanation.
Это уже часть каждого KnowledgeRevision.
Можно извлечь без изменений.
```

### Option C: Separate audit projection

```
Потребует:
- Новая таблица / проекция
- Запись при создании revision
- Изменение Pipeline

Влияние на Platform:
- Новый Projection + builder
- Изменение композиции
- ⚠ Platform files changed > 0
```

### Option D: Event log

```
Потребует:
- Event sourcing инфраструктуры
- Отдельного event store
- Новый Bootstrap

Влияние на Platform: значительное. Не для v1.
```

**Вывод для v1:** Option A + Option B
- Чтение revision history из существующей таблицы
- Consistency Check — вычисляется на лету (stateless)
- Provenance — из KnowledgeSnapshot внутри revision
- 0 изменений Platform

## 4. Capability Boundary

### Responsibility: Knowledge Audit Trail Capability

```
✓ Чтение revision history (через существующий Repository)
✓ Чтение source_document_id, metadata, created_at
✓ Чтение provenance из KnowledgeSnapshot
✓ Выполнение Consistency Check (лёгкий)
✓ Формирование AuditRecord из существующих данных
✓ Детерминированный результат
✓ Пагинация
```

### NOT Responsibility

```
✗ Хранение audit данных (v1 — только чтение)
✗ Модификация Knowledge
✗ Trust scoring
✗ Approval workflow
✗ User action logging (требует event system)
✗ Semantic conflict detection
```

### Invariant: Platform files changed = 0

| Компонент | Изменяется? | Обоснование |
|-----------|:-----------:|-------------|
| Domain | ❌ | не затрагивается |
| KnowledgeRevision | ❌ | read-only |
| KnowledgeSnapshot | ❌ | read-only |
| Repository Protocol | ❌ | достаточно get() / get_by_document_id() |
| Projection | ❌ | не затрагивается |
| Bootstrap | ❌ | не затрагивается |

**Прогноз:** Audit Trail v1 укладывается в Capability layer
без изменения Platform.

## 5. Audit Model

```python
@dataclass(frozen=True)
class AuditProvenanceEntry:
    source_type: str
    source_id: str
    description: str
    confidence: float

@dataclass(frozen=True)
class AuditRevisionEntry:
    revision_id: str
    revision_number: int
    created_at: str
    created_by: str
    reason: str
    source_document_id: str

@dataclass(frozen=True)
class AuditValidationEntry:
    check_timestamp: str
    is_consistent: bool
    violations_count: int
    errors: int
    warnings: int

@dataclass(frozen=True)
class AuditTrailResult:
    """Full audit trail for a given revision."""
    revision: AuditRevisionEntry
    provenance: tuple[AuditProvenanceEntry, ...]
    validation: AuditValidationEntry | None
    previous_revision: AuditRevisionEntry | None
    next_revision: AuditRevisionEntry | None
    all_revisions_count: int
```

## 6. Trust Integration

Связь: Consistency Check → Audit Trail

```
Consistency Check               Audit Trail
────────────────────────────────────────────────
check_snapshot_consistency()     part of AuditResult
returns:                         as AuditValidationEntry
  is_consistent
  violations
  errors/warnings

Audit Trail v1:
  └── выполняет Consistency Check на лету
  └── включает результат в AuditTrailResult
  └── НЕ сохраняет результат (каждый раз пересчитывает)
```

**Почему пересчёт, а не хранение?**
- Consistency Check — stateless pure function
- Выполняется за миллисекунды (только structural checks)
- Не требует storage
- 0 изменений Platform

**Когда понадобится хранение:**
- Когда проверки станут дорогими (cross-revision, semantic)
- Когда нужна история проверок
- Тогда — ADR + новая проекция

## 7. Persistence Question

**Ответ для v1: отдельный storage НЕ нужен.**

```
Используемые источники:
────────────────────────────────
knowledge_revisions таблица:
    revision_id, revision_number, source_document_id,
    created_at, metadata (JSONB)

KnowledgeSnapshot (из KnowledgeRevision):
    provenance.chain.links
    graph.nodes / graph.edges

Всё это уже существует. Никаких новых таблиц, индексов или миграций.
```

**Что потребовало бы новый storage:**
- Сохранение Consistency Check результатов → новая таблица audit_log
- История выполнения → projection + event
- Оба варианта — c ADR и Platform changes

**Decision:** отложить storage до появления требования "хранить историю проверок".

## 8. API Surface

```
GET /knowledge/audit/{revision_id}
  → AuditTrailResult

GET /knowledge/audit/{revision_id}/provenance
  → provenance chain (из KnowledgeSnapshot)

GET /knowledge/audit/{revision_id}/validation
  → Consistency Check result (computed on the fly)
```

Response (GET /knowledge/audit/{revision_id}):

```json
{
    "revision": {
        "revision_id": "rev-003",
        "revision_number": 3,
        "created_at": "2026-03-10T09:15:00",
        "created_by": "alice",
        "reason": "Corrected cadastral number",
        "source_document_id": "doc-001"
    },
    "provenance": [
        {"source_type": "document", "source_id": "doc-001",
         "description": "Purchase Agreement", "confidence": 1.0}
    ],
    "validation": {
        "check_timestamp": "2026-07-21T12:00:00",
        "is_consistent": true,
        "violations_count": 0,
        "errors": 0,
        "warnings": 0
    },
    "previous_revision": {
        "revision_id": "rev-002",
        "revision_number": 2,
        "created_at": "2026-02-01T14:30:00",
        "reason": "Added buyer entity"
    },
    "next_revision": {
        "revision_id": "rev-004",
        "revision_number": 4,
        "created_at": "2026-04-05T16:45:00",
        "reason": "Agreement signed"
    },
    "all_revisions_count": 5
}
```

## 9. Validation Plan

### Acceptance Criteria

```
□ Platform files changed = 0
□ ADR required = No
□ Architecture Review = No
□ Existing regressions = PASS
□ Audit trail returns revision metadata
□ Audit trail returns provenance from snapshot
□ Audit trail runs consistency check on the fly
□ Audit trail shows previous / next revision
□ Deterministic result (same revision → same audit)
□ Explorer compatibility preserved
□ Timeline compatibility preserved
□ Diff compatibility preserved
□ Search compatibility preserved
□ Traversal compatibility preserved
□ Consistency compatibility preserved
□ Covered by tests
```

### Invariants

```
Audit(nonexistent revision) → 404
Audit(existing revision) → always includes revision + provenance
Validation check is computed on demand (not cached)
Previous/next based on created_at ASC ordering
```

## 10. GO / NO-GO Criteria

```
Knowledge Audit Trail v1

Capability layer only:     ✅ (read-only, pure functions)
Platform changes:          0  (прогноз)
ADR:                       No (прогноз)
Source of Truth:           Existing knowledge_revisions + KnowledgeSnapshot
Execution:                 on-demand (API)
Persistence:               Не требуется (stateless)
Storage:                   Отложен до требования "хранить историю проверок"

GO / NO-GO decision:       ?
```

### Architectural Objective

Knowledge Audit Trail v1 validates that the Platform can explain
the origin, history, and quality of its Knowledge using only
existing data models, without modifying Domain, Persistence,
or writing any new projections.

This shifts the Capability layer from **validation** to **explanation**:

```
Cycle 1:  Knowledge Operations  — locate · navigate · compare · find
Cycle 2:  Connectivity          — connect
Cycle 3:  Integrity             — validate
Cycle 4:  Trust & Recovery      — audit / explain
```
