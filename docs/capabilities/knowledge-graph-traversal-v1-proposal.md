# Knowledge Graph Traversal v1 — Capability Proposal

```
Status            PROPOSED (Phase 0)
Capability        Knowledge Graph Traversal v1
──────────────────────────────────────────────
Architecture      v2.3.1
Baseline
──────────────────────────────────────────────
Cycle             2 (Knowledge Connectivity)
──────────────────────────────────────────────
Date              2026-07-21
```

## 1. Graph Intent

Что такое traversal в контексте Realtoros?

**Primary intent v1:**
Найти KnowledgeRevision, связанные с заданной Entity или другим узлом графа,
через существующие Graph Edges, и предоставить цепочку связей.

Пользовательские сценарии:

- "Покажи все KnowledgeNode, связанные с этой сущностью"
- "Какие ещё документы упоминают того же buyer?"
- "Найди все revision, где фигурирует этот кадастровый номер"
- "Построй цепочку: Документ → Сделка → Участники → Другие сделки"

**Deferred (not v1):**
- Произвольный graph traversal (BFS/DFS над всей историей)
- Semantic inference
- Path discovery между произвольными узлами
- Graph analytics

## 2. Graph Source of Truth

Где находятся связи?

**Option A: KnowledgeGraph внутри KnowledgeSnapshot (рекомендован для v1)**

```
Преимущества:
- граф уже существует в каждом snapshot
- nodes и edges уже построены
- Identity Contract уже определён: (node_type, domain_id)
- 0 изменений Platform

Недостатки:
- граф живёт внутри одной revision
- чтобы найти связи между revision, нужен второй шаг (поиск по logical identity)
- не оптимизирован для traversal (хранится как tuple, не индекс)
```

**Option B: ProjectionStore — ENTITY / AGREEMENT проекции**

```
Преимущества:
- entity и agreement проекции уже материализованы
- содержат domain_id

Недостатки:
- проекции — key-value, не оптимизированы для связей
- edge-информация есть только в Graph, не в ProjectionDTO
```

**Option C: Domain relations (недоступно)**

Domain не знает о графе. Graph строится в RevisionSnapshotFactory.

**Option D: Отдельный Graph Storage (Neo4j / Edge Store)**

Ранний. Нужен ADR.

**Вывод:** Option A — единственный, не требующий изменения Platform.

## 3. Capability Boundary

### Что может быть реализовано в Capability layer

```
Чтение KnowledgeGraph из KnowledgeSnapshot:
  ✓ snapshot.graph.nodes — tuple[GraphNode, …]
  ✓ snapshot.graph.edges — tuple[GraphEdge, …]

Сопоставление узлов по logical identity:
  ✓ (node_type, domain_id) — контракт из Diff

Поиск связанных revision:
  ✓ SQL: WHERE metadata->>'entities' ILIKE %domain_id%
  ✓ или через source_document_id

Построение TraversalResult:
  ✓ цепочка: Node → Edge → RelatedNode
  ✓ список связанных revision
```

### Проверка инварианта: Platform files changed = 0

| Компонент | Изменяется? | Обоснование |
|-----------|:-----------:|-------------|
| Domain | ❌ | не затрагивается |
| KnowledgeRevision | ❌ | не затрагивается |
| KnowledgeSnapshot | ❌ | не затрагивается |
| GraphNode / GraphEdge | ❌ | используются как read models |
| Projection DTO | ❌ | не затрагивается |
| Repository Protocol | ❌ | не затрагивается |
| ProjectionStore | ❌ | не затрагивается |
| Materialization | ❌ | не затрагивается |
| Bootstrap | ❌ | не затрагивается |

**Прогноз:** Traversal v1 укладывается в Capability layer без изменения Platform.

## 4. Traversal Model (предварительная, без реализации)

```python
@dataclass(frozen=True)
class TraversalNode:
    """A node encountered during traversal."""
    node_type: str
    domain_id: str
    label: str
    revision_ids: tuple[str, ...]  # revisions where this node appears

@dataclass(frozen=True)
class TraversalEdge:
    """An edge traversed."""
    source_type: str
    source_domain: str
    edge_type: str
    target_type: str
    target_domain: str

@dataclass(frozen=True)
class TraversalRequest:
    """Request to traverse the Knowledge Graph."""
    # Starting point
    node_type: str | None = None
    domain_id: str | None = None
    revision_id: str | None = None  # alternative: start from a revision

    # Controls
    max_depth: int = 1
    edge_types: tuple[str, ...] = ()  # empty = all
    limit: int = 50

@dataclass(frozen=True)
class TraversalResult:
    """Result of graph traversal."""
    root: TraversalNode
    nodes: tuple[TraversalNode, ...]  # all discovered nodes
    edges: tuple[TraversalEdge, ...]  # all traversed edges
    revisions: tuple[str, ...]        # all revision IDs involved
```

**v1 ограничен depth=1 (direct neighbours).**
Depth > 1 может привести к combinatorial explosion без индексации.

## 5. Complexity Boundary

### Included in v1

```
✓ Direct relations (1-hop traversal from a node)
✓ Traversal from entity (node_type + domain_id)
✓ Traversal from revision (extract all entities, then traverse)
✓ List of related KnowledgeRevision
✓ Deterministic ordering
✓ Pagination
✓ Consistent with Identity Contract (node_type, domain_id)
```

### Excluded from v1

```
✗ Multi-hop traversal (depth > 1 — deferred)
✗ Arbitrary graph algorithms (BFS, DFS)
✗ Path discovery between two arbitrary nodes
✗ Graph analytics (centrality, clusters)
✗ Semantic inference
✗ Recommendation engine
✗ Visual graph rendering (frontend, not capability)
```

## 6. Persistence Question

Достаточно ли PostgreSQL для v1?

**Ответ: Да.**

Алгоритм для v1:

1. Получить KnowledgeSnapshot (revision_id → repository.get → snapshot)
2. Извлечь граф: snapshot.graph.nodes, snapshot.graph.edges
3. Найти стартовый узел по logical identity (node_type, domain_id)
4. Пройти по edges из того же snapshot
5. Для каждого найденного узла — найти revision, где он встречается
   (SQL: поиск по проекциям или через репозиторий)

**PostgreSQL достаточно.** Рекурсивные запросы (WITH RECURSIVE CTE) для multi-hop — deferred.

**Что НЕ требуется для v1:**
- Graph database (Neo4j)
- Materialized views
- Новые индексы (существующие достаточны)

## 7. API Surface (предварительный контракт)

```
GET /knowledge/traversal?node_type=entity&domain_id=ent-xxx
  → TraversalResult (nodes, edges, revisions)

GET /knowledge/traversal?revision_id=rev-xxx
  → извлечь entities из revision, затем traverse

GET /knowledge/traversal/{revision_id}/related
  → список связанных revisions
```

Response:

```json
{
    "root": {"node_type": "entity", "domain_id": "ent-seller", "label": "Seller Corp"},
    "nodes": [
        {"node_type": "entity", "domain_id": "ent-buyer", "label": "Buyer LLC"},
        {"node_type": "agreement", "domain_id": "agr-001", "label": "Contract #1"}
    ],
    "edges": [
        {"source": "ent-seller", "type": "participates", "target": "agr-001"},
        {"source": "ent-buyer", "type": "participates", "target": "agr-001"}
    ],
    "revisions": ["rev-001", "rev-005", "rev-012"]
}
```

Стиль: следует patterns Explorer / Timeline / Diff / Search.

## 8. Identity Contract (наследуется от Diff)

```
Node logical identity: (node_type, domain_id)  — стабилен
Edge identity:         (source_key, edge_type, target_key)  — семантический
```

Traversal использует те же ключи, что Diff.
Никакого нового Identity Contract не требуется.

## 9. Validation Plan

### Acceptance Criteria

```
□ Platform files changed = 0
□ ADR required = No
□ Architecture Review = No
□ Existing regressions = PASS
□ Traversal from entity returns correct neighbours
□ Traversal from revision extracts entities first
□ 1-hop only (depth=1 enforced)
□ Deterministic results
□ Explorer compatibility preserved
□ Timeline compatibility preserved
□ Diff compatibility preserved
□ Search compatibility preserved
□ Covered by tests
```

### Invariants

```
Traversal(unknown entity) → empty result
Traversal(entity with no edges) → root only
Traversal(revision) → all entities in that revision as root set
Same input → same output (deterministic)
```

## 10. Architectural Objective

Knowledge Graph Traversal v1 validates that the Platform
supports relation discovery across KnowledgeRevision objects
using the existing Graph model and Identity Contract.

This is the natural evolution of the Capability layer:

```
Cycle 1 (v2.3.1):        Operations on KnowledgeRevision objects
  Explorer     — locate
  Timeline     — navigate
  Diff         — compare
  Search       — find

Cycle 2 (v2.4):          Operations between KnowledgeRevision objects
  Traversal    — discover relationships
```

If this capability can be implemented with Platform files changed = 0,
it validates that the existing KnowledgeGraph model in KnowledgeSnapshot
is sufficient for relation discovery without a separate graph store.

## Phase 0 Verdict

```
Knowledge Graph Traversal v1

Baseline compatibility:    PASS (предварительно)
Platform changes:          0 (предварительно)
ADR:                       No (предварительно)
Implementation:            ? (ожидает GO / NO-GO)
```
