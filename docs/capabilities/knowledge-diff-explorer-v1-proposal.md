# Knowledge Diff Explorer v1 — Capability Proposal

```
Status            PROPOSED (Phase 0)
Capability        Knowledge Diff Explorer v1
──────────────────────────────────────────────
Architecture      v2.3.1
Baseline
──────────────────────────────────────────────
Branch            feature/knowledge-diff-explorer-v1
──────────────────────────────────────────────
Date              2026-07-20
```

## 1. Goal

Показать пользователю, что изменилось между двумя Revisions.

Пользователь уже может:
- Explorer: видеть состояние одной Revision
- Timeline: перемещаться между Revisions

Следующий вопрос: **"Что именно изменилось?"**

## 2. Architectural Objective

Knowledge Diff Explorer validates that the Platform supports
structural comparison between two KnowledgeSnapshots without
modifying either the snapshots or the Domain models.

Третья независимая read-oriented Capability. В отличие от Explorer
(просмотр) и Timeline (навигация), Diff требует **вычисления разницы**
между двумя неизменяемыми состояниями.

## 3. What counts as a change?

### Graph — Nodes

| Изменение | Обозначение | Критерий |
|-----------|:-----------:|----------|
| Node added | `+` | node_id существует в new, отсутствует в old |
| Node removed | `-` | node_id существует в old, отсутствует в new |
| Node updated | `~` | node_id в обоих, но node_type / domain_id / attributes различаются |

### Graph — Edges

| Изменение | Обозначение | Критерий |
|-----------|:-----------:|----------|
| Edge added | `+` | edge_id в new, отсутствует в old |
| Edge removed | `-` | edge_id в old, отсутствует в new |
| Edge updated | `~` | (не реализовано в v1 — edge immutable после создания) |

### Provenance

| Изменение | Критерий |
|-----------|----------|
| Link added | graph_node_id + source_type появились в new |
| Link removed | graph_node_id + source_type пропали |

### Explanation

| Изменение | Критерий |
|-----------|----------|
| Text changed | step.summary / reasons / evidence различаются |
| Step added/removed | step_number отсутствует в одной из версий |

### Что НЕ делается в v1

- merge revisions
- visual graph diff
- conflict resolution
- semantic similarity
- fuzzy matching

v1 — полностью детерминированная. Diff не модифицирует Snapshot,
только вычисляет разницу между двумя неизменяемыми состояниями.

## 4. Fits Baseline?

- [x] Domain не изменяется
- [x] KnowledgeRevision не изменяется
- [x] KnowledgeSnapshot не изменяется
- [x] Projection DTO не изменяются
- [x] Repository Protocol не изменяется
- [x] ProjectionStore не изменяется
- [x] Materialization не изменяется
- [x] Query DSL / Engine не изменяются
- [x] Bootstrap не изменяется

## 5. Baseline Check

| Компонент | Изменяется? |
|-----------|:-----------:|
| Domain | ❌ |
| KnowledgeSnapshot | ❌ |
| Projection | ❌ |
| Repository | ❌ |
| Bootstrap | ❌ |

## 6. API

```http
GET /knowledge/diff?left={revision_id}&right={revision_id}
```

Response:

```json
{
    "left_revision_id": "...",
    "right_revision_id": "...",
    "nodes": {
        "added": [{"node_id": "...", "node_type": "...", ...}],
        "removed": [{"node_id": "...", ...}],
        "updated": [{"node_id": "...", "changes": {"field": {"old": "...", "new": "..."}}}]
    },
    "edges": {
        "added": [...],
        "removed": [...]
    },
    "provenance": {
        "added": [...],
        "removed": [...]
    },
    "explanation": {
        "steps_added": [...],
        "steps_removed": [...],
        "steps_changed": [...]
    }
}
```

## 7. DTO (ViewModel, не Domain)

```
DiffResult
    ├── left_revision_id: str
    ├── right_revision_id: str
    ├── nodes: NodeDiff
    │       ├── added: list[NodeSummary]
    │       ├── removed: list[NodeSummary]
    │       └── updated: list[NodeChange]
    ├── edges: EdgeDiff
    ├── provenance: ProvenanceDiff
    └── explanation: ExplanationDiff
```

## 8. Implementation Plan

### Phase 0 — Validation

#### Identity Contract

Заменяет исходный раздел "Node ID stability".

Logical:
```
Logical identity (Domain):
    (node_type, domain_id)        ← стабилен между ревизиями

Snapshot identity (Graph):
    node_id = uuid.uuid4()         ← НЕ стабилен между ревизиями

Diff uses:
    logical identity               ← (node_type, domain_id)
```

Обоснование:
- `GraphNodeFactory` создаёт `node_id = GraphNodeId.generate() = str(uuid.uuid4())`
  — случайный UUID при каждом вызове. Один и тот же логический объект
  получает разный `node_id` в разных ревизиях.
- `domain_id` — стабильный идентификатор, формируется из доменного ID
  (например `"ent-doc001-0"`, `"agr-abc"`). Не меняется между ревизиями.

Вопрос: достаточно ли `domain_id` одного, или нужен `(node_type, domain_id)`?

В Domain `domain_id` формируется с префиксом (`ent-`, `agr-`, `fact-`),
поэтому коллизий между типами быть не должно. Однако для формальной
корректности контракт использует составной ключ `(node_type, domain_id)`.

**Вывод Phase 0: `node_id` НЕ стабилен. Ключ сравнения: `(node_type, domain_id)`.**

```
Phase 0 Result
───────────────────────────────────────
Initial assumption:       node_id is logical identity
Validation:               FAILED
Architecture impact:      None
Correct logical identity: (node_type, domain_id)
Platform modifications:   0
ADR:                      Not required
Capability contract:      Updated
Implementation:           APPROVED
```

#### Node updated — definition

`same (node_type, domain_id) + payload differs = updated`.

В v1 сравниваются следующие поля:
- `node_type` (ENTITY / AGREEMENT / DOCUMENT / …)
- `domain_id`
- `attributes.label`
- `attributes.display_name`
- `attributes.tags`
- `attributes.properties`

Не сравниваются:
- `metadata.created_at` (всегда разный между ревизиями)
- `metadata.created_by`
- `metadata.schema_version`

`NodeProvenance` и `GraphMetadata` считаются служебными и не входят
в diff v1.

#### Edge ID stability

Проверить: гарантируется ли, что `edge_id` является стабильным
идентификатором отношения?

`GraphEdge.edge_id` = `GraphEdgeId(value=str(uuid.uuid4()))` —
создаётся случайный UUID при каждом построении.

**Вывод**: **edge_id НЕ стабилен между ревизиями.**
Сравнение ребер должно выполняться по семантическому ключу.

#### Edge uniqueness invariant

Проверить: может ли существовать более одного ребра с одинаковой
тройкой `(source_node_id, edge_type, target_node_id)`?

Если **нет** — ключ `(source, type, target)` достаточен для v1.
Если когда-нибудь появятся параллельные рёбра с разными весами,
интервалами действия или confidence — потребуется расширение ключа.

**Ожидание**: тройка уникальна в рамках одного Snapshot.
Ключ `(source_node_id, edge_type, target_node_id)` корректен для v1.

#### Explanation step identity

Проверить: есть ли у шагов стабильный идентификатор?

`ExplanationStep.step_number` — порядковый номер. Если шаги
всегда добавляются в конец с монотонным номером, сравнение по
`step_number` корректно. Если порядок может меняться — нужен
более сложный контракт.

**Ожидание**: `step_number` стабилен и монотонен. Сравнение
по `step_number` корректно.

### T1 — Diff Logic (stateless functions)
- `diff_nodes(old_nodes, new_nodes) → NodeDiff`
- `diff_edges(old_edges, new_edges) → EdgeDiff`
- `diff_provenance(old_prov, new_prov) → ProvenanceDiff`
- `diff_explanation(old_exp, new_exp) → ExplanationDiff`

### T2 — API endpoint
- `GET /knowledge/diff?left={rev_id}&right={rev_id}`
- Чтение обоих Revision через Repository
- Вызов функций diff
- Возврат DiffResult

### T3 — Tests
- Unit: все 4 diff-функции (добавление, удаление, обновление)
- API: 200, 404 для missing revision, edge cases
- Regression: 983 → N

## 9. Acceptance Criteria

### Diff invariants

```
A vs A                 → empty diff
Diff(A, B)             → deterministic (same input, same output)
Diff(A, B)             → independent of iteration order
Snapshot unchanged     → read-only comparison, no mutation
```

### Checklist

```
□ Platform files changed = 0
□ ADR required = No
□ Architecture Review = No
□ Existing regressions = PASS
□ Diff deterministic (same input → same output)
□ Graph comparison deterministic
□ Snapshot unchanged (read-only comparison)
□ Explorer compatibility preserved
□ Timeline compatibility preserved
□ Covered by tests
```

## 10. Capability Report

```
Capability        Knowledge Diff Explorer v1
────────────────────────────────────────────
Status            COMPLETE
────────────────────────────────────────────
Platform changes  0
────────────────────────────────────────────
ADR               Not required
────────────────────────────────────────────
Architecture      Not required
Review
────────────────────────────────────────────
Regression        1056 / 1056 PASS
────────────────────────────────────────────
Date              2026-07-21
```

Итоговый отчёт: `docs/capabilities/knowledge-diff-explorer-v1.md`
