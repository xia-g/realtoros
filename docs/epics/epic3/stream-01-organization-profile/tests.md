# Stream 1 — Organization Profile: Test Strategy

> **Статус:** 🔵 Proposal Approved — Tests Pending
> **Создан:** 2026-07-23
> **Связанный proposal:** `proposal.md`

## Test pyramid

```
    ╱╲
   ╱ e2e ╲             3 теста (API)
  ╱────────╲
 ╱ integration ╲        8 тестов (repository + DB)
╱────────────────╲
╱   unit (domain)  ╲    12 тестов (model + service)
╱────────────────────╲
```

## 1. Unit tests — Domain model

**Категория:** `compliance/tests/unit/test_domain.py`

| # | Тест | Проверка |
|:-:|:-----|:---------|
| 1 | `test_create_organization_profile` | Все поля заполняются корректно |
| 2 | `test_entity_type_enum` | EntityType.ip, .ooo, .group, .branch |
| 3 | `test_tax_regime_enum` | Все 6 значений TaxRegime |
| 4 | `test_reporting_period_enum` | monthly, quarterly, yearly |
| 5 | `test_organization_id_default` | Если не передан — генерируется UUID |
| 6 | `test_organization_id_immutability` | После создания не меняется |
| 7 | `test_settings_default_empty_dict` | settings по умолчанию пустой dict |

## 2. Unit tests — Service layer

**Категория:** `compliance/tests/unit/test_services.py`

| # | Тест | Проверка |
|:-:|:-----|:---------|
| 1 | `test_create_organization_success` | Полный flow: validate → save → return |
| 2 | `test_create_organization_duplicate_inn` | DuplicateInnError |
| 3 | `test_create_organization_invalid_inn_legal` | InvalidInnError (10 digits) |
| 4 | `test_create_organization_invalid_inn_ip` | InvalidInnError (12 digits) |
| 5 | `test_get_organization_success` | Возвращает профиль |
| 6 | `test_get_organization_not_found` | OrganizationNotFoundError |
| 7 | `test_update_organization_partial` | Partial update — только переданные поля |
| 8 | `test_delete_organization` | Успешное удаление |
| 9 | `test_list_organizations_pagination` | Пагинация работает |
| 10 | `test_list_organizations_empty` | Пустой список |

## 3. Integration tests — Repository

**Категория:** `compliance/tests/integration/test_repository.py`

| # | Тест | Проверка |
|:-:|:-----|:---------|
| 1 | `test_repository_save_and_get` | Сохранить → прочитать |
| 2 | `test_repository_save_and_update` | Update существующей записи |
| 3 | `test_repository_delete` | Delete → get возвращает None |
| 4 | `test_repository_find_by_inn` | Поиск по ИНН |
| 5 | `test_repository_list_with_pagination` | offset + limit |
| 6 | `test_repository_inn_unique_constraint` | DB-level unique violation |
| 7 | `test_repository_get_or_raise_success` | get_or_raise возвращает профиль |
| 8 | `test_repository_get_or_raise_not_found` | get_or_raise кидает исключение |

## 4. API tests — E2E

**Категория:** `compliance/tests/integration/test_api.py`

| # | Тест | Проверка |
|:-:|:-----|:---------|
| 1 | `test_create_organization` | POST → 201 + response body |
| 2 | `test_get_organization` | GET → 200 |
| 3 | `test_get_organization_404` | GET несуществующего → 404 |
| 4 | `test_update_organization` | PUT → 200 |
| 5 | `test_delete_organization` | DELETE → 204 |
| 6 | `test_list_organizations` | GET list → 200 + pagination |
| 7 | `test_create_organization_validation` | POST с некорректными данными → 422 |
| 8 | `test_create_organization_duplicate_inn` | POST с существующим ИНН → 409 |

## 5. Repository Contract Tests (для downstream)

**Категория:** `compliance/tests/contract/test_repository_contract.py`

```python
# Абстрактный тест — все реализации проходят один набор
class OrganizationProfileRepositoryContractTests:

    @abstractmethod
    def make_repo(self) -> IOrganizationProfileRepository:
        ...

    async def test_crud_cycle(self): ...
    async def test_uniqueness(self): ...
    async def test_pagination(self): ...
```

Используется:
- SQLAlchemy реализацией (integration)
- In-memory реализацией (unit, для downstream)
- Cache-proxy реализацией (если будет)

## Запуск

```bash
# Все тесты Compliance
pytest backend/compliance/tests/ -v

# Только unit
pytest backend/compliance/tests/unit/ -v

# Только integration (требует БД)
pytest backend/compliance/tests/integration/ -v

# С coverage
pytest backend/compliance/tests/ -v --cov=backend.compliance
```

## CI gates

| Gate | Порог | Команда |
|:-----|:------|:--------|
| Unit tests | 100% pass | `pytest tests/unit/ -v` |
| Integration tests | 100% pass | `pytest tests/integration/ -v` |
| Coverage (domain + application) | ≥ 90% | `pytest --cov=compliance.domain --cov=compliance.application` |
| No imports from ORM in domain | Check | `grep -r "sqlalchemy" compliance/domain/` |
