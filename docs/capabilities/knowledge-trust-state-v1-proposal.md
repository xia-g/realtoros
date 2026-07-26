# Knowledge Trust State v1 — Capability Proposal

```
Status            PROPOSED (Phase 0)
Capability        Knowledge Trust State v1
──────────────────────────────────────────────
Architecture      v2.6
Baseline
──────────────────────────────────────────────
Cycle             5 (Knowledge Recovery)
──────────────────────────────────────────────
Date              2026-07-21
```

## 1. Trust Intent

Что такое Trust State?

**Primary intent v1:**
Вычислить текущее доверие к KnowledgeRevision на основе
существующих проверок и метаданных — без изменения Knowledge.

Trust как оценка системы, а не факт внутри знания.

### Trust levels (v1)

| Level | Meaning | Условие |
|:-----:|---------|---------|
| `VALID` | Knowledge можно использовать | Все structural checks пройдены, provenance полный |
| `WARNING` | Знание есть, но с оговорками | Есть orphan nodes, missing provenance, self-references |
| `INVALID` | Знание содержит ошибки | Есть broken edges, duplicate nodes, invalid relations |
| `UNKNOWN` | Недостаточно данных | Snapshot пустой или не проверялся |

### Deferred (not v1)

- Numeric trust score (0.0–1.0)
- Semantic trust (conflict detection)
- Provenance-based trust weighting
- Actor reputation
- Time-decay trust

## 2. Source of Truth

### For v1 — compute on demand from:

```
KnowledgeSnapshot
        │
        ├── graph.nodes / graph.edges        (для structural checks)
        ├── provenance.chain.links           (для provenance coverage)
        └── explanation.steps               (для explanation coverage)
                │
                ▼
ConsistencyCheckResult
        │
        ├── is_consistent
        ├── errors count
        └── warnings count
                │
                ▼
TrustState (computed)
        │
        ├── status: VALID | WARNING | INVALID | UNKNOWN
        ├── reasons: tuple[str, ...]
        └── evaluated_at: str
```

**Нужен ли storage?** Нет для v1. Всё вычисляется на лету.

**Когда понадобится storage:**
- Для сравнения trust state между проверками
- Для отслеживания изменения доверия
- Тогда — новая проекция или audit_log таблица (ADR)

## 3. Trust Model

```python
@dataclass(frozen=True)
class TrustState:
    status: str               # "VALID" | "WARNING" | "INVALID" | "UNKNOWN"
    reasons: tuple[str, ...]
    evaluated_at: str
    structural_errors: int = 0
    structural_warnings: int = 0
    node_count: int = 0
    edge_count: int = 0
    provenance_coverage: float = 0.0  # 0.0–1.0

@dataclass(frozen=True)
class TrustEvaluation:
    revision_id: str
    trust: TrustState
    has_provenance: bool
    has_explanation: bool
    revision_count: int = 0
```

### Status determination rules (v1)

```
IF snapshot empty or no nodes:
    status = UNKNOWN

ELIF any broken_edge or duplicate_node or invalid_relation:
    status = INVALID

ELIF any orphan_node or missing_provenance or self_reference:
    status = WARNING

ELSE all checks pass:
    status = VALID
```

## 4. Capability Boundary

### Responsibility: Knowledge Trust State Capability

```
✓ Вычисление TrustState на основе Consistency Check
✓ Оценка provenance coverage
✓ Оценка explanation coverage
✓ Детерминированный результат
✓ Формирование причин (reasons) для каждого статуса
```

### NOT Responsibility

```
✗ Хранение TrustState (v1 — только вычисление)
✗ Изменение Knowledge
✗ Trust scoring engine
✗ Actor reputation
✗ Time-decay
✗ Approval workflow trigger
✗ Repair decision
```

### Invariant: Platform files changed = 0

| Компонент | Изменяется? | Обоснование |
|-----------|:-----------:|-------------|
| Domain | ❌ | не затрагивается |
| KnowledgeSnapshot | ❌ | read-only input |
| Repository | ❌ | достаточно get() |
| ConsistencyCheck | ❌ | переиспользуется как есть |
| Audit Trail | ❌ | переиспользуется как есть |
| Bootstrap | ❌ | не затрагивается |

**Прогноз:** Trust State v1 укладывается в Capability layer
без изменения Platform.

## 5. Determinism

### Invariant

```
same KnowledgeSnapshot + same ruleset = same TrustState
```

Гарантируется:
- Consistency Check уже детерминирован
- Trust State использует только его результат + простые метрики
- Нет случайности, нет external state, нет времени в правилах

### Sorting

Reasons отсортированы по severity → type.

## 6. Future Compatibility

Trust State будет использоваться:

```
Trust State
       │
       ├── Governance (v2.8)
       │     └── "Какие изменения требуют approval?"
       │         Критерий: Trust State != VALID
       │
       ├── Repair eligibility (v2.9)
       │     └── "Какие нарушения можно исправить автоматически?"
       │         Критерий: Trust State == INVALID (structural only)
       │
       ├── Search ranking (future)
       │     └── "Какие revision показывать в первую очередь?"
       │         Критерий: VALID > WARNING > INVALID > UNKNOWN
       │
       └── UI indicators
             └── "Показать статус доверия пользователю"
```

## 7. Persistence Question

**Ответ:** Нет, отдельный storage не нужен для v1.

| Компонент | Источник | Хранится? |
|-----------|:--------:|:---------:|
| Graph | KnowledgeSnapshot | да (JSONB) |
| ConsistencyCheck | computed on demand | нет |
| TrustState | computed on demand | нет |
| Provenance coverage | computed on demand | нет |

**Когда понадобится storage:**
- Когда нужна история TrustState (сравнение "было/стало")
- Когда TrustState нужен для Governance (триггер approval)
- Оба случая — ADR + новая проекция или таблица

## 8. API Surface

```
GET /knowledge/trust/{revision_id}
  → TrustEvaluation

GET /knowledge/trust/latest
  → последняя revision
```

Response:

```json
{
    "revision_id": "rev-003",
    "trust": {
        "status": "WARNING",
        "reasons": ["2 orphan nodes detected", "1 missing provenance link"],
        "evaluated_at": "2026-07-21T12:00:00",
        "structural_errors": 0,
        "structural_warnings": 3,
        "node_count": 5,
        "edge_count": 3,
        "provenance_coverage": 0.6
    },
    "has_provenance": true,
    "has_explanation": true,
    "revision_count": 7
}
```

## 9. Validation Plan

### Acceptance Criteria

```
□ Platform files changed = 0
□ ADR required = No
□ Architecture Review = No
□ Existing regressions = PASS
□ VALID for a well-formed snapshot
□ WARNING for orphan/missing provenance
□ INVALID for broken edges/duplicates
□ UNKNOWN for empty snapshot
□ Deterministic (same snapshot → same trust)
□ Explorer compatibility preserved
□ Timeline compatibility preserved
□ Diff compatibility preserved
□ Search compatibility preserved
□ Traversal compatibility preserved
□ Consistency compatibility preserved
□ Audit compatibility preserved
□ Covered by tests
```

### Test cases

```
✓ Valid snapshot → VALID
✓ Broken edge → INVALID
✓ Orphan node → WARNING
✓ Missing provenance → WARNING
✓ Empty graph → UNKNOWN
✓ Deterministic (same input)
✓ Stable reasons ordering
```

## 10. GO / NO-GO Criteria

```
Knowledge Trust State v1

Capability layer only:     ✅ (stateless, pure functions)
Platform changes:          0  (прогноз)
ADR:                       No (прогноз)
Source of Truth:           KnowledgeSnapshot + ConsistencyCheck
Execution:                 on-demand (API)
Storage:                   Not required for v1
Read-only:                 ✅ (no mutation)
```

### Architectural Objective

Knowledge Trust State v1 shifts the Capability layer from
**explanation** ("why does this knowledge exist?") to
**evaluation** ("can this knowledge be trusted?").

This completes the transition from data access to data quality
and prepares the foundation for Governance and Repair cycles:

```
v2.3  Access     — locate · navigate · compare · find
v2.4  Structure  — connect
v2.5  Quality    — validate
v2.6  Trust      — explain
v2.7  Trust      — evaluate          ← here
v2.8  Governance — control
v2.9  Recovery   — change
```
