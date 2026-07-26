# Knowledge Governance v1 — Capability Proposal

```
Status            PROPOSED (Phase 0)
Capability        Knowledge Governance v1
──────────────────────────────────────────────
Architecture      v2.7
Baseline
──────────────────────────────────────────────
Cycle             6 (Knowledge Control)
──────────────────────────────────────────────
Date              2026-07-21
```

## 1. Governance Intent

Что такое Governance в контексте Realtoros?

**Primary intent v1:**
Определить, допустимо ли изменение Knowledge на основе
текущего Trust State и набора правил — без мутации Knowledge.

Governance отвечает на вопрос:
"Можно ли создать новую KnowledgeRevision на основе
текущего состояния?"

**Governance = decision layer. Не mutation layer.**

Сценарии v1:

```
Trust State (VALID)
    │
    ▼
Proposed change (new revision from document)
    │
    ▼
Governance decision:
    ├── APPROVED — change is safe
    ├── FLAGGED — requires human review
    └── REJECTED — change would degrade trust
```

**Deferred (not v1):**
- Approval workflow (multi-step)
- Actor-based rules (user X can approve)
- Escalation
- Governance audit trail storage

## 2. Governance Scope

### Included in v1

```
✓ Trust State → decision mapping
✓ Rule: VALID → APPROVED
✓ Rule: WARNING → FLAGGED (requires review)
✓ Rule: INVALID → REJECTED (block change)
✓ Rule: UNKNOWN → FLAGGED (insufficient data)
✓ Deterministic decision output
```

### Excluded from v1

```
✗ Multi-step approval workflow
✗ Actor identity / permissions
✗ Escalation rules
✗ Governance record storage
✗ Automatic change execution
✗ Notification system
```

## 3. Source of Truth

### Governance uses (read-only):

```
TrustState
    │
    ├── status: VALID | WARNING | INVALID | UNKNOWN
    ├── structural_errors
    ├── structural_warnings
    └── provenance_coverage
            │
            ▼
GovernanceRules (code, not storage)
    │
    ├── if VALID → APPROVED
    ├── if WARNING → FLAGGED (requires review)
    ├── if INVALID → REJECTED
    └── if UNKNOWN → FLAGGED
            │
            ▼
GovernanceDecision (computed)
    │
    ├── decision: APPROVED | FLAGGED | REJECTED
    ├── reason
    └── based_on: TrustState
```

**Нужен ли storage?** Нет для v1. Решение вычисляется на лету.

**Когда понадобится storage:**
- Для истории решений (Governance Audit)
- Для approval tracking
- Для учета, сколько решений было принято/отклонено

## 4. Capability Boundary

### Responsibility: Knowledge Governance Capability

```
✓ Принять TrustState + proposed change context
✓ Применить GovernanceRules
✓ Вернуть GovernanceDecision
✓ Детерминированный результат
```

### NOT Responsibility

```
✗ Хранение решений
✗ Мутация Knowledge
✗ Actor permission management
✗ Approver notification
✗ Change execution
✗ Escalation
✗ Создание KnowledgeRevision
```

### Invariant: Platform files changed = 0

| Компонент | Изменяется? |
|-----------|:-----------:|
| Domain | ❌ |
| KnowledgeSnapshot | ❌ (read-only) |
| TrustState | ❌ (входной параметр) |
| Repository | ❌ |
| Bootstrap | ❌ |

**Прогноз:** Governance v1 — чистый decision layer, не требующий
изменения Platform.

## 5. Governance Model

```python
@dataclass(frozen=True)
class GovernanceDecision:
    decision: str             # "APPROVED" | "FLAGGED" | "REJECTED"
    reason: str
    based_on_trust: str       # "VALID" | "WARNING" | "INVALID" | "UNKNOWN"
    structural_errors: int = 0
    structural_warnings: int = 0
    provenance_coverage: float = 0.0
```

### Rules (v1)

```
VALID     → APPROVED   (safe to change)
WARNING   → FLAGGED    (can change, requires review)
INVALID   → REJECTED   (block change — knowledge integrity broken)
UNKNOWN   → FLAGGED    (cannot decide — needs human)
```

## 6. Trust Integration

Governance — первый потребитель Trust State в production:

```
Trust State
    ↓
Consistency
    ↓
Audit Trail
    ↓
Governance ← здесь
    ↓
Decision
```

Без Trust State Governance не имеет смысла.
Trust State — источник данных для принятия решений.

## 7. Persistence Question

**Ответ:** Не нужен для v1.

Governance — stateless decision layer:
- Принимает TrustState на вход
- Возвращает GovernanceDecision
- Не сохраняет ничего

**Когда понадобится:**
- История Governance решений → новая таблица
- Approval tracking → workflow storage
- Оба случая — ADR

## 8. API Surface

```
GET /knowledge/governance/check/{revision_id}
  → GovernanceDecision

POST /knowledge/governance/assess
  {
    "revision_id": "...",
    "proposed_change": "new_document" | "repair" | "update"
  }
  → GovernanceDecision
```

Response:

```json
{
    "decision": "REJECTED",
    "reason": "Knowledge is INVALID: 2 broken edges detected",
    "based_on_trust": "INVALID",
    "structural_errors": 2,
    "structural_warnings": 0,
    "provenance_coverage": 0.5
}
```

## 9. Validation Plan

### Acceptance Criteria

```
□ Platform files changed = 0
□ ADR required = No
□ Architecture Review = No
□ Existing regressions = PASS
□ VALID trust → APPROVED
□ INVALID trust → REJECTED
□ WARNING trust → FLAGGED
□ UNKNOWN trust → FLAGGED
□ Deterministic (same trust → same decision)
□ Trust compatibility preserved
□ Consistency compatibility preserved
□ Audit compatibility preserved
□ Covered by tests
```

### Test cases

```
✓ VALID → APPROVED
✓ INVALID → REJECTED
✓ WARNING → FLAGGED
✓ UNKNOWN → FLAGGED
✓ Deterministic output
✓ Reason matches trust state
```

## 10. GO / NO-GO Criteria

```
Knowledge Governance v1

Capability layer only:     ✅ (pure decision, stateless)
Platform changes:          0  (прогноз)
ADR:                       No (прогноз)
Source of Truth:           TrustState (computed)
Mutation:                  None (decisions only)
Storage:                   Not required for v1
Execution:                 on-demand (API)
```

### Architectural Objective

Knowledge Governance v1 validates that the Platform can
support change control decisions based on existing Trust State
without modifying Domain, Persistence, or introducing mutation.

This is the transition from observe/analyze to decide/control:

```
v2.3  Access        — locate · navigate · compare · find
v2.4  Structure     — connect
v2.5  Quality       — validate
v2.6  Trust         — explain
v2.7  Trust State   — evaluate
v2.8  Governance    — decide          ← here
v2.9  Recovery      — change
```
