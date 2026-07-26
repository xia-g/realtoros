# Stream 1 — Organization Profile: Implementation Plan

> **Статус:** 🔵 Proposal Approved — Implementation Pending
> **Создан:** 2026-07-23
> **Связанный proposal:** `proposal.md`

## Этапы реализации

### T1 — Domain model + Enums + Errors

- [ ] Создать `compliance/domain/enums.py` — `EntityType`, `TaxRegime`, `ReportingPeriod`
- [ ] Создать `compliance/domain/models.py` — `OrganizationProfile` dataclass
- [ ] Создать `compliance/domain/errors.py` — `OrganizationNotFoundError`, `DuplicateInnError`, `InvalidInnError`
- [ ] Написать unit-тесты для domain

### T2 — Repository interface

- [ ] Создать `compliance/application/interfaces.py` — `IOrganizationProfileRepository` ABC
- [ ] Убедиться: 0 импортов из SQLAlchemy/FastAPI

### T3 — Application service

- [ ] Создать `compliance/application/services.py` — `OrganizationService`
- [ ] Написать unit-тесты с in-memory repository

### T4 — Persistence (SQL)

- [ ] Создать миграцию: `compliance.organization_profiles` table
- [ ] Создать `compliance/infrastructure/persistence/tables.py` — ORM mapping
- [ ] Создать `compliance/infrastructure/persistence/repository.py` — SQLAlchemy implementation
- [ ] Написать integration-тесты

### T5 — FastAPI endpoints

- [ ] Создать `compliance/api/schemas.py` — Pydantic models
- [ ] Создать `compliance/api/routes.py` — FastAPI router
- [ ] Связать с `backend/api/router.py`
- [ ] Написать e2e тесты

### T6 — Migration script from public.companies

- [ ] Написать скрипт начального импорта
- [ ] Протестировать на staging data

### T7 — In-memory repository (для downstream)

- [ ] Создать `compliance/infrastructure/persistence/in_memory.py`
- [ ] Использовать в тестах downstream Streams

## Зависимости

| Этап | Зависит от | Блокирует |
|:-----|:-----------|:----------|
| T1 | — | T2, T3 |
| T2 | T1 | T3 |
| T3 | T1, T2 | T4 |
| T4 | T3 | T5 |
| T5 | T4 | — |
| T6 | T4 | Stream 2 |
| T7 | T2 | Streams 2-11 tests |

## Оценка

| Этап | Предполагаемая трудоёмкость |
|:-----|:---------------------------|
| T1 | 0.5 дня |
| T2 | 0.25 дня |
| T3 | 0.5 дня |
| T4 | 1 день |
| T5 | 0.5 дня |
| T6 | 0.5 дня |
| T7 | 0.25 дня |
| **Итого** | **~3.5 дня** |
