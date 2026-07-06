# Architecture Review Checklist

**Одна страница. Каждый пункт — вопрос на code review.**

## Dependency Rules

| # | Вопрос | Нарушение |
|---|--------|-----------|
| □ | Не появился ли импорт снизу вверх? | Domain не должен знать о Projection, Query, Engine, Infrastructure |
| □ | Не начал ли Infrastructure импортироваться Domain? | Domain импортирует только stdlib |
| □ | Не появилась ли циклическая зависимость? | A→B→A — всегда ошибка |
| □ | Не начал ли Projection импортировать Query или Engine? | Projection может знать только Domain |
| □ | Не начал ли Query импортировать Engine? | Query — декларация, не вычисление |

## Source of Truth

| # | Вопрос | Нарушение |
|---|--------|-----------|
| □ | Не стала ли Projection источником истины? | Source of truth = Domain (v2.0) |
| □ | Не появились ли бизнес-факты в Projection? | Факты только в Domain |
| □ | Не редактируется ли Projection вручную? | Projection immutable, только rebuild |
| □ | Не хранит ли Projection данные, отсутствующие в Domain? | Все данные вычислимы из Domain |
| □ | Не создаёт ли Projection знания? | Projection — read model, не создаёт |

## CQRS

| # | Вопрос | Нарушение |
|---|--------|-----------|
| □ | Не смешались ли Command и Query? | QueryService.read() ≠ RefreshService.rebuild() |
| □ | Не появился ли `get_or_rebuild()` в QueryService? | Query — только read. Rebuild — команда |
| □ | Не мутирует ли Query Domain? | Query read-only, никаких side effects |
| □ | Не стал ли Engine писать напрямую в Store? | Engine → Executor → Store |

## Domain Integrity

| # | Вопрос | Нарушение |
|---|--------|-----------|
| □ | Не появились ли mutable Domain объекты? | Fact, Revision, KnowledgeState — immutable |
| □ | Не появилась ли бизнес-интерпретация в Facts? | DOCUMENT_HAS_*, не SELLS/OWNS |
| □ | Не нарушен ли инвариант детерминизма? | same input → same output |
| □ | Не появился ли ручной create_node/create_edge? | Только через GraphBuilder |
| □ | Не появился ли append-only нарушен? | Revisions, Events только добавляются |

## Engine Integrity

| # | Вопрос | Нарушение |
|---|--------|-----------|
| □ | Не начал ли Planner выполнять код? | Planner строит ExecutionPlan, не выполняет |
| □ | Не изменил ли Optimizer семантику? | Optimized ≡ Original |
| □ | Не появился ли SQL/Cypher в ExecutionPlan? | Plan — domain terms, не технологии |
| □ | Не потерялась ли Explainability при оптимизации? | Все annotation сохранены |
| □ | Не появился ли backend reference в Plan? | `ProjectionRef(type)`, не `SELECT * FROM` |

## ADR Compliance

| # | Вопрос | Нарушение |
|---|--------|-----------|
| □ | Нарушен ли какой-либо ADR? | Проверить ADR-001 — ADR-016 |
| □ | Нарушен ли какой-либо инвариант? | Проверить D1–D10, P1–P10, Q1–Q12, E1–E10 |
| □ | Требуется ли новое ADR? | Изменение архитектуры → новое ADR |
| □ | Есть ли breaking change без ADR? | Любой breaking change требует ADR |

## Technology Independence

| # | Вопрос | Нарушение |
|---|--------|-----------|
| □ | Не появился ли PostgreSQL/Neo4j в Engine? | Engine — domain terms, не SQL |
| □ | Не появился ли импорт конкретной БД? | Только в Infrastructure (v2.1.4) |
| □ | Не стал ли Infrastructure частью Domain? | Infrastructure = adapters |

## Testing

| # | Вопрос | Нарушение |
|---|--------|-----------|
| □ | Есть ли тесты для новых инвариантов? | Каждый инвариант → тест |
| □ | Все ли ADR покрыты тестами? | ADR → решение → тест решения |
| □ | Domain тесты работают без Infrastructure? | Чистые unit-тесты, без БД |
| □ | Добавлены ли тесты на детерминизм? | same input + same revision → same output |

## Legend

- ✅ — всё верно
- ❌ — блокирующее нарушение (не merge)
- ⚠️ — требует ADR перед merge
- ❓ — требует обсуждения
