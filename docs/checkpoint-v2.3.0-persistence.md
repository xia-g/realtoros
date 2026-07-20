# Checkpoint v2.3.0 — Persistence Layer Complete

## Реализовано

- ✅ PostgreSQL KnowledgeRevisionRepository
- ✅ PostgreSQL ProjectionStore
- ✅ JSONB persistence
- ✅ Manual codecs
- ✅ Memory implementations сохранены
- ✅ DI-compatible infrastructure
- ✅ Materialization работает без изменений
- ✅ QueryEngine работает без изменений
- ✅ Domain не изменялся
- ✅ Projection DTO не изменялись
- ✅ Query DSL не изменялся
- ✅ Query Planner не изменялся
- ✅ Business Logic не изменялась

## Покрытие

| Компонент | Статус |
|-----------|--------|
| PostgreSQL Repository | ✅ |
| PostgreSQL ProjectionStore | ✅ |
| Infrastructure | ✅ |
| Memory compatibility | ✅ |
| Full regression | ✅ 960 tests |

## Теги

- `v2.2.0-runtime-snapshot` — DomainPipelineBridge fix
- `v2.3.0-postgresql-revision-repository` — 12 integration tests
- `v2.3.0-postgresql-projection-store` — 16 integration tests
- `v2.3.0-persistence` — umbrella tag (pushed to origin)

## Следующая ветка

**feature/v2.3-runtime-bootstrap**

Цель: после перезапуска процесса восстанавливать состояние из PostgreSQL,
а не пересоздавать всё заново.

```
Application start
    ↓
PostgreSQL
    ↓
KnowledgeRevisionRepository
    ↓
ProjectionStore
    ↓
Runtime ready
    ↓
QueryEngine
```

Без повторного OCR, Semantic Processing, Deal Resolution, Materialization.
