# Knowledge Consistency Check v1 — Capability Proposal

```
Status            PROPOSED (Phase 0)
Capability        Knowledge Consistency Check v1
──────────────────────────────────────────────
Architecture      v2.4
Baseline
──────────────────────────────────────────────
Cycle             3 (Knowledge Integrity)
──────────────────────────────────────────────
Date              2026-07-21
```

## 1. Integrity Intent

Что означает "Knowledge is consistent"?

Для v1 — **structural consistency**: все ссылки внутри KnowledgeSnapshot
ведут к существующим объектам, граф не содержит разрывов, метаданные
корректны.

Категории нарушений (по сложности):

| Категория | Пример | v1 |
|-----------|--------|:--:|
| Broken reference | Edge указывает на несуществующий node_id | ✅ |
| Invalid type | Edge соединяет несовместимые node_type | ✅ |
| Orphan node | Node не связан ни с одним edge | ✅ |
| Duplicate node | Два узла с одинаковым (node_type, domain_id) | ✅ |
| Missing provenance | Node не имеет provenance link | ✅ |
| Orphan revision | Revision без source_document_id | deferred |
| Invalid lifecycle | Revision_number не соответствует created_at | deferred |
| Conflicting states | Два знания противоречат друг другу | deferred (semantic) |

**Primary intent v1:** проверить structural consistency одного
KnowledgeSnapshot — целостность ссылок внутри графа.

## 2. Consistency Scope

### Structural consistency (v1)

```
✓ Edge references valid node_id (source + target exist in same graph)
✓ Provenance link references valid graph_node_id
✓ No duplicate logical nodes (same node_type + domain_id)
✓ Edge does not reference itself (source != target)
✓ Revision has metadata (created_at, created_by)
✓ Explanation steps reference valid graph_node_id
✓ Node has at least node_type and domain_id (fields not empty)
```

### Domain consistency (deferred)

```
✗ Node type allowed for domain (ENTITY vs AGREEMENT semantics)
✗ Edge type valid for source/target node types
✗ Revision lifecycle correct (number progression)
```

### Semantic consistency (deferred)

```
✗ Two facts contradict each other
✗ State conflicts between revisions
```

## 3. Source of Truth

### Option A: KnowledgeSnapshot / KnowledgeGraph (рекомендован для v1)

```
Преимущества:
- snapshot уже содержит полный граф
- все проверки выполняются над одним объектом
- stateless: проверка = pure function(snapshot) → violations
- 0 изменений Platform

Недостатки:
- не видит cross-revision проблемы
- не знает о семантике домена
```

### Option B: Domain models

```
Не применимо для v1 — Domain не содержит графа.
Domain состоит из изолированных dataclass без cross-references.
```

### Option C: Projection layer

```
Преимущества:
- содержит материализованные entity/agreement данные
- можно проверить соответствие snapshot ↔ projection

Недостатки:
- projection — read model, а не source of truth
- расхождение snapshot ↔ projection — не ошибка, а ожидаемое поведение
```

### Option D: Отдельный validation storage

```
Преждевременно. Только после измерения типов нарушений.
```

**Вывод:** Option A — единственный, не требующий изменения Platform.

## 4. Capability Boundary

### Responsibility: Knowledge Consistency Capability

```
✓ Определение списка проверок
✓ Выполнение stateless проверок над KnowledgeSnapshot
✓ Формирование ConsistencyViolation с severity
✓ Детерминированный результат
✓ Рекомендации по исправлению (опционально)
```

### NOT Responsibility

```
✗ Изменение Domain model
✗ Изменение Repository
✗ Изменение Projection
✗ Автоматическое исправление нарушений
✗ Семантические проверки (v1)
✗ Cross-revision checks (v1)
```

### Invariant: Platform files changed = 0

| Компонент | Изменяется? | Обоснование |
|-----------|:-----------:|-------------|
| Domain | ❌ | не затрагивается |
| KnowledgeSnapshot | ❌ | read-only input |
| KnowledgeGraph | ❌ | read-only input |
| GraphNode / GraphEdge | ❌ | только чтение |
| Repository | ❌ | не затрагивается |
| ProjectionStore | ❌ | не затрагивается |
| Bootstrap | ❌ | не затрагивается |

**Прогноз:** Consistency Check v1 укладывается в Capability layer
без изменения Platform.

## 5. Consistency Model (без реализации)

```python
@dataclass(frozen=True)
class ConsistencyViolation:
    severity: str               # "error" | "warning" | "info"
    violation_type: str          # "broken_edge" | "orphan_node" | ...
    message: str                 # human-readable description
    affected_node_type: str | None = None
    affected_domain_id: str | None = None
    affected_field: str | None = None
    expected: str | None = None
    actual: str | None = None

@dataclass(frozen=True)
class ConsistencyCheckRequest:
    revision_id: str | None = None   # если None — последняя
    checks: tuple[str, ...] = ()     # empty = все

@dataclass(frozen=True)
class ConsistencyCheckResult:
    revision_id: str
    is_consistent: bool
    violations: tuple[ConsistencyViolation, ...] = ()
    checks_performed: int = 0
    errors: int = 0
    warnings: int = 0
```

Deterministic: одинаковый snapshot → одинаковый список violations.

## 6. Execution Model

**v1: по запросу пользователя (Option A).**

```
GET /knowledge/consistency?revision_id=xxx
  → ConsistencyCheckResult
```

Причина:
- stateless проверка не требует фоновых задач
- пользователь проверяет конкретную revision по необходимости
- deferred: после каждого изменения (Option B), периодически (Option C)

## 7. Persistence Question

**Ответ:** PostgreSQL достаточен, но для v1 вообще не нужен.

```
Consistency Check v1:
- читает KnowledgeSnapshot через Repository (get by id)
- выполняет stateless проверки над snapshot.graph
- возвращает результат

Никакого отдельного storage, индексов или миграций не требуется.
```

Что может потребоваться позже:
- Таблица violation log (для отслеживания истории)
- Background job для периодических проверок
- Trigger при создании revision

Для v1 — ничего из этого не нужно.

## 8. API Surface (предварительный контракт)

```
GET /knowledge/consistency/{revision_id}
  → ConsistencyCheckResult

GET /knowledge/consistency/latest
  → проверка последней revision
```

Response:

```json
{
    "revision_id": "rev-xxx",
    "is_consistent": false,
    "violations": [
        {
            "severity": "error",
            "violation_type": "broken_edge",
            "message": "Edge references non-existent node_id 'missing-uuid'",
            "affected_node_type": null,
            "affected_domain_id": null,
            "affected_field": "target_node"
        },
        {
            "severity": "warning",
            "violation_type": "orphan_node",
            "message": "Node 'ent-seller' (entity) has no incoming or outgoing edges",
            "affected_node_type": "entity",
            "affected_domain_id": "ent-seller"
        }
    ],
    "checks_performed": 8,
    "errors": 1,
    "warnings": 1
}
```

## 9. Validation Plan

### Acceptance Criteria

```
□ Platform files changed = 0
□ ADR required = No
□ Architecture Review = No
□ Existing regressions = PASS
□ Deterministic violations (same input → same list)
□ Stable ordering (violations sorted by severity → type → entity)
□ All structural checks listed in scope v1
□ Explorer compatibility preserved
□ Search compatibility preserved
□ Traversal compatibility preserved
□ Covered by tests
```

### Test cases

```
✓ All checks pass on a well-formed snapshot
✓ Broken edge detected (source/target node_id missing)
✓ Orphan node detected (no edges connected)
✓ Duplicate logical node detected
✓ Self-referencing edge detected
✓ Empty graph → no violations (not an error)
✓ Deterministic ordering
```

## 10. GO / NO-GO Criteria

```
Knowledge Consistency Check v1

Capability layer only:     ✅ (stateless pure functions)
Platform changes:          0  (прогноз)
ADR:                       No (прогноз)
Source of Truth:           KnowledgeSnapshot / KnowledgeGraph
Execution:                 on-demand (API)
Persistence:               PostgreSQL достаточен (PS not needed for v1)

GO / NO-GO decision:       ?
```

### Architectural Objective

Knowledge Consistency Check v1 validates that the Platform
supports self-diagnosis of Knowledge structural integrity
using only existing data models, without modifying Domain,
Persistence, or Projection models.

This shifts the Capability layer from production of Knowledge
(Explorer → locate, Timeline → navigate, Diff → compare,
Search → find, Traversal → connect) to **validation** of Knowledge:

```
Cycle 1:  Operations ON KnowledgeRevision
          locate · navigate · compare · find

Cycle 2:  Operations BETWEEN KnowledgeRevision
          connect

Cycle 3:  Quality OF Knowledge
          validate
```
