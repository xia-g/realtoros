# Capability Template

## 1. Goal

Одна строка: что делает эта Capability для пользователя.

## 2. Architectural Objective

Почему эта Capability важна для архитектуры, а не только для пользователя.
Какую проверку Baseline она проводит.

## 3. Fits Baseline?

- [ ] Domain не изменяется
- [ ] KnowledgeRevision не изменяется
- [ ] KnowledgeSnapshot не изменяется
- [ ] Projection DTO не изменяются
- [ ] Repository Protocol не изменяется
- [ ] ProjectionStore не изменяется
- [ ] Materialization не изменяется
- [ ] Query DSL / Engine не изменяются
- [ ] Bootstrap не изменяется

## 4. Baseline Check

| Компонент | Изменяется? |
|-----------|:-----------:|
| Domain | ❌ |
| KnowledgeSnapshot | ❌ |
| Projection | ❌ |
| Repository | ❌ |
| Bootstrap | ❌ |

## 5. API

```http
GET /knowledge/...
```

## 6. DTO

Структура ответа (ViewModel).

## 7. Implementation Plan

### Phase 0 — Validation
### T1
### T2
### ...

## 8. Acceptance Criteria

```
□ Platform files changed = 0
□ ADR required = No
□ Architecture Review = No
□ Existing regressions = PASS
□ Covered by tests
□ (Capability-specific criteria)
```

## 9. Capability Report

```
Capability        (name)
────────────────────────────
Status            COMPLETE
────────────────────────────
Platform changes  0
────────────────────────────
Regression        N / N PASS
```

Сохранять как `docs/capabilities/<name>-v1-proposal.md` → `docs/capabilities/<name>-v1.md`.
