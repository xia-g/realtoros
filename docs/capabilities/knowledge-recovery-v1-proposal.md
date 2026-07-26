# Knowledge Recovery v1 — Capability Proposal

```
Status            PROPOSED (Phase 0)
Capability        Knowledge Recovery v1
──────────────────────────────────────────────
Architecture      v2.8
Baseline
──────────────────────────────────────────────
Cycle             7 (Knowledge Recovery)
──────────────────────────────────────────────
Date              2026-07-21
```

## 1. Recovery Intent

Что такое Recovery?

**Primary intent v1:**
Создать новую корректирующую KnowledgeRevision для исправления
структурных нарушений после прохождения:

```
Consistency Check
        ↓
Trust State
        ↓
Governance Decision (APPROVED)
        ↓
Recovery ← здесь
        ↓
New KnowledgeRevision
        ↓
Audit Trail
```

**Что такое Recovery?** Recovery — это не редактирование базы данных,
а контролируемый lifecycle шаг, который создаёт новую версию Knowledge
с исправлениями, сохраняя полную историю предыдущего состояния.

### Scope v1

```
Included:
✓ Исправление structural violations
  - broken edges (удаление)
  - duplicate nodes (удаление дубликата)
  - orphan nodes (связывание или удаление)
✓ Создание новой KnowledgeRevision после исправления
✓ Governance approval required
✓ Audit Trail linkage
✓ Immutable old revision

Excluded:
✗ Semantic repair (conflict resolution)
✗ Automatic repair (без Governance)
✗ Rollback (отмена изменений)
✗ Migration of Knowledge state
✗ Repair of multiple revisions
✗ Batch repair
```

## 2. Mutation Boundary

### Критическое решение: Где появляется первая запись?

**Option A: Recovery создаёт новую KnowledgeRevision (рекомендован)**

```
Обнаружено нарушение → Repair → Новая Revision
                                  ├── snapshot = исправленная копия
                                  ├── metadata.reason = "repair: <type>"
                                  ├── metadata.created_by = "system"
                                  └── ссылка на исходную revision
```

**Option B: Recovery изменяет существующую Revision (ОТКЛОНЁН)**

Нарушает immutable history. Нарушает audit trail.

**Option C: Recovery создаёт Repair Proposal без изменения**

Промежуточный шаг (может быть добавлен позже как dry-run).

### Принцип:

```
Recovery не исправляет прошлое.
Recovery создаёт новое состояние, сохраняющее историю.
```

## 3. Source of Truth

### Порядок исправления:

```
Detect:  Consistency Check → violations
         │
Assess:  Trust State → trust level
         │
Decide:  Governance → APPROVED | REJECTED
         │
Execute: Recovery → новая KnowledgeRevision
         │
Record:  Audit Trail → repair entry
```

### Что является основой исправления:

```
Source of Truth for repair:
    KnowledgeSnapshot (исходный)
        + ConsistencyViolation (что не так)
        + GovernanceDecision (разрешено ли)
        = RecoveryPlan (что делать)

Source of Truth for result:
    Новая KnowledgeRevision (immutable)
```

## 4. Capability vs Domain Boundary

### Responsibility: Knowledge Recovery Capability

```
✓ Создание RecoveryPlan на основе violations
✓ Применение Governance решения
✓ Создание исправленной копии KnowledgeSnapshot
✓ Создание новой KnowledgeRevisionRecord
✓ Audit Trail linkage
```

### NOT Responsibility

```
✗ Изменение существующих Revision
✗ Обход Governance
✗ Semantic repair
✗ Batch operations
✗ Automatic execution (без approval)
```

### Invariant: Platform files changed = 0 — ??

**Здесь впервые возникает вопрос: может ли Recovery быть реализован
без изменения Platform?**

Для создания новой Revision требуется `Repository.save()`.
Repository Protocol уже существует:
```python
def save(self, record: KnowledgeRevisionRecord) -> None
```

Recovery может:
1. Прочитать существующую Revision (get)
2. Создать исправленную копию snapshot
3. Создать новый KnowledgeRevision с новым ID
4. Сохранить через repo.save()

**Всё это использует существующие инструменты Platform.**
Domain model не изменяется.
Repository Protocol не расширяется.
Bootstrap не затрагивается.

| Компонент | Изменяется? | Обоснование |
|-----------|:-----------:|-------------|
| Domain | ❌ | не затрагивается |
| KnowledgeRevision | ❌ | новый экземпляр, не изменение класса |
| KnowledgeSnapshot | ❌ | новая копия |
| Repository Protocol | ❌ | save() уже существует |
| Repository | ❌ | используется как есть |
| Bootstrap | ❌ | не затрагивается |
| Pipeline | ❌ | не затрагивается |

**Прогноз:** Recovery v1 может быть реализован в Capability layer
с использованием существующих контрактов.

**Единственное, что может потребовать Platform change:**
- Repair-specific projection (если нужно хранить историю repair)
— deferred до v1.1

## 5. Recovery Model

```python
@dataclass(frozen=True)
class RepairAction:
    action_type: str           # "remove_broken_edge" | "remove_duplicate" | "remove_orphan"
    violation_type: str        # original violation type
    target_id: str             # edge_id or node_id
    description: str

@dataclass(frozen=True)
class RecoveryPlan:
    source_revision_id: str
    governance_decision: str   # "APPROVED" | "REJECTED"
    actions: tuple[RepairAction, ...]
    snapshot_patch: str         # description of changes

@dataclass(frozen=True)
class RecoveryResult:
    source_revision_id: str
    recovery_revision_id: str   # новая Revision
    actions_performed: int
    audit_message: str
```

## 6. Safety Model

### Гарантии v1

```
✓ Immutable old revision       — never modified
✓ New revision after repair    — created with new ID
✓ Governance approval required — REPLACED without → error
✓ Audit entry                  — new revision linked to source
✓ Deterministic repair         — same violation → same fix
✓ Rollback possibility         — old revision always exists
```

### Безопасность

```
RecoveryPlan → dry-run first (optional)
GovernanceDecision.APPROVED → required
Recovery creates NewRevision → not mutation
```

## 7. Execution Model

**Option for v1: Approved execution (Option B)**

```
1. POST /knowledge/recovery/plan/{revision_id}
   → RecoveryPlan (what would be fixed, dry-run)

2. POST /knowledge/recovery/execute/{revision_id}
   Body: { governance_check: true }
   → RecoveryResult or error if governance fails
```

**Dry-run is always available:**
```
GET /knowledge/recovery/plan/{revision_id}
→ shows what would be done without executing
```

**Deferred: automatic repair (Option C) — requires Policy Engine**

## 8. Persistence Question

**Нужны ли новые таблицы для v1?**

| Объект | Хранится в | Новое? |
|--------|:-----------:|:------:|
| Исходная Revision | knowledge_revisions | существующая |
| Новая Revision | knowledge_revisions | новая запись |
| Repair link | metadata предыдущей/new revision | поле `reason` |
| Audit | вычисляется на лету | не хранится |

**Ответ:** новых таблиц для v1 не требуется.
Repair создаёт обычную KnowledgeRevisionRecord, которая сохраняется
в существующую таблицу через существующий `repo.save()`.

**Что потребует новых таблиц (deferred):**
- Repair history log
- Recovery events
- Все три — ADR + Platform change

## 9. API Surface

```
GET /knowledge/recovery/plan/{revision_id}
  → RecoveryPlan (dry-run, no changes)

POST /knowledge/recovery/execute/{revision_id}
  → RecoveryResult (creates new revision)
  Body: { governance_check: true }
```

Response (dry-run plan):

```json
{
    "source_revision_id": "rev-003",
    "governance_decision": "APPROVED",
    "actions": [
        {
            "action_type": "remove_broken_edge",
            "violation_type": "broken_edge",
            "target_id": "edge-missing-ref",
            "description": "Remove edge referencing non-existent node"
        },
        {
            "action_type": "remove_orphan_node",
            "violation_type": "orphan_node",
            "target_id": "node-ent-orphan",
            "description": "Remove entity node with no connections"
        }
    ]
}
```

## 10. Validation Plan

### Acceptance Criteria

```
□ Platform files changed = 0
□ ADR required = No
□ Architecture Review = No
□ Existing regressions = PASS
□ Recovery plan shows violations correctly
□ Governance check required before execution
□ Governance REJECTED → execution blocked
□ Governance APPROVED → new revision created
□ Old revision remains immutable
□ New revision linked to source via metadata
□ New revision passes Consistency Check
□ Audit Trail shows repair entry
□ Deterministic repair (same violation → same fix)
□ All existing capabilities compatible
□ Covered by tests
```

### Test cases

```
✓ Dry-run plan for broken revision
✓ Governance REJECTED → execution blocked
✓ Governance APPROVED → new revision created
✓ Old revision unchanged after repair
✓ New revision is consistent (passes check)
✓ New revision has source reference
✓ Multiple violations all addressed
```

## 11. GO / NO-GO Criteria

```
Knowledge Recovery v1

Controlled mutation:       ✅ (new revision, not edit)
Governance required:        ✅
Immutable history:          ✅ (old revision untouched)
Platform changes:           0 (прогноз)
ADR:                        No (прогноз — пока нет новых таблиц)
Storage:                    Existing tables sufficient
Execution:                  Approved only (dry-run available)
```

### Architectural Objective

Knowledge Recovery v1 is the transition point where the system
moves from READ / ANALYZE / DECIDE to CONTROLLED CHANGE.

The key architectural invariant:

```
Old KnowledgeRevision → immutable
Repair → new KnowledgeRevision with source link
Audit Trail → complete history
```

This is the most significant architectural boundary crossed
since the Baseline was frozen at v2.3.1.
```
