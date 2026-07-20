# Runtime Recovery / Bootstrap — Architectural Audit

## 1. Где создаются MemoryKnowledgeRevisionRepository и MemoryProjectionStore?

| Файл | Строка | Контекст | Repo? | Store? |
|------|--------|----------|:-----:|:------:|
| `application/knowledge_persistence/integrator.py` | 87-88 | `KnowledgeRuntimeIntegrator.__init__()` | ✅ | ✅ |
| `application/knowledge_persistence/runtime_integration.py` | 55-56 | `build_pipeline_components()` | ✅ | ✅ |
| `tests/knowledge_persistence/` | мн. | Fixture в каждом тесте | ✅ | ✅ |
| `tests/projection/` | мн. | `InMemoryProjectionStore()` (другое имя) | — | ✅ |
| `tests/infrastructure/` | мн. | Integration fixture | ✅ | ✅ |
| `application/e2e_projection_integration.py` | 169 | `run_v21_e2e_pipeline()` | — | ✅ |
| `infrastructure/composition_root.py` | 29 | `ProjectionStoreFactory` | — | ✅ |

**Главная точка в production**: `KnowledgeRuntimeIntegrator.__init__()` (integrator.py:87-88). Именно этот экземпляр используется в uploads.py как singleton на уровне модуля (lazy init при первом запросе).

---

## 2. Где происходит инициализация?

Инициализация происходит **лениво** — при первом вызове `/api/v1/upload/job/{job_id}`.

В `backend/api/routes/uploads.py:578-586`:

```python
_mod = _sys.modules.get(__name__)
if not hasattr(_mod, "_v21_integrator"):
    _integrator = KnowledgeRuntimeIntegrator()
    _mod._v21_integrator = _integrator
else:
    _integrator = _mod._v21_integrator
```

Никакой инициализации при старте FastAPI-приложения не происходит.

---

## 3. Как устроен startup приложения?

Файл: `backend/main.py` (lifespan функция).

```
lifespan(app):
    configure_logging()
    DatabaseHealthCheck.check()       ← проверка, что PostgreSQL отвечает
    register_sync_handlers()          ← event handlers
    startup_health_check()            ← non-blocking, логирует результаты
    yield                             ← приложение работает
    logger.info("application_stopping")
```

**Нет**: инициализации KnowledgeRuntime, подключения Repository, загрузки ProjectionStore.

---

## 4. Какие компоненты создаются при запуске?

```
KnowledgeRuntimeIntegrator.__init__():
    revision_repository = MemoryKnowledgeRevisionRepository()   ← ПУСТОЙ
    projection_store = MemoryProjectionStore()                  ← ПУСТОЙ
    registry = ProjectionRegistry()
        + MaterializedEntityBuilder
        + MaterializedAgreementBuilder
        + MaterializedGraphBuilder
        + MaterializedProvenanceBuilder
    plan = BuildPlan (ENTITY → AGREEMENT → GRAPH → PROVENANCE)
```

Схематично:

```
KnowledgeRuntimeIntegrator
    ├── revision_repository: MemoryKnowledgeRevisionRepository {}
    ├── projection_store:     MemoryProjectionStore {}
    ├── registry:             ProjectionRegistry [4 builders]
    └── plan:                 BuildPlan [4 steps]
```

Никаких данных. Только пустые коллекции.

---

## 5. Где правильная точка подключения PostgreSQL Repository и ProjectionStore?

**Три кандидата**:

| Место | Pro | Contra |
|-------|-----|--------|
| A. В `lifespan()` (backend/main.py) | Единая точка старта, DB уже проверена | KnowledgeRuntime — отдельный слой, не стоит смешивать с HTTP |
| B. В `KnowledgeRuntimeIntegrator.__init__()` | Минимальное изменение, замена Memory → PostgreSQL | Нет способа передать DSN/connection |
| C. В `composition_root.py` | Существующая фабрика, DI-ready | PostgreSQL store уже зарегистрирован как "not implemented" |

**Рекомендация: B + C.** 
- `KnowledgeRuntimeIntegrator` принимает `dsn` в конструкторе.
- Если DSN передан — использует PostgreSQL реализации.
- Если нет — Memory (сохранение обратной совместимости).
- `composition_root` расширяется для поддержки PostgreSQL.

---

## 6. После запуска: что должно восстанавливаться?

```
После рестарта:
    PostgreSQL
        ├── knowledge_revisions table    ←  все Revision
        └── projection_store table       ←  все Projection

Application start
    ↓
Подключиться к PostgreSQL
    ↓
Загрузить revision_repository из таблицы knowledge_revisions
    ↓
Загрузить projection_store из таблицы projection_store
    ↓
Создать KnowledgeQueryEngine (остаётся stateless)
    ↓
Runtime ready — можно сразу выполнять QueryEngine
```

**Что не восстанавливается** (и не должно):
- DomainPipelineBridge (stateless, создаётся на каждый документ)
- OCR state
- Semantic state
- Deal Resolution state
- Materialization (ProjectionStore уже в БД)

---

## 7. Требуется ли повторная materialization после рестарта?

**НЕТ.** ProjectionStore в PostgreSQL уже содержит все материализованные проекции.

Единственный кейс, когда materialization может понадобиться — если схема Projection изменилась (schema_version). Но в v2.3 это не предусмотрено — schema_version зафиксирована.

**Критическое свойство**: если `save()` и `materialize()` выполнялись в одном цикле (как сейчас), то Projection всегда соответствует Revision. PostgreSQL это сохраняет.

---

## 8. Что сегодня хранится только в памяти и теряется?

| Данные | Где | Живёт | Теряется? |
|--------|-----|-------|:---------:|
| `KnowledgeRevisionRecord` | `MemoryKnowledgeRevisionRepository._store` | Время жизни Integrator | ✅ |
| `Projection` | `MemoryProjectionStore._data` | Время жизни Integrator | ✅ |
| `ProjectionDigest` | `MemoryProjectionStore._digests` | Время жизни Integrator | ✅ |
| `ProjectionRegistry` | `KnowledgeRuntimeIntegrator._registry` | Время жизни Integrator | ✅ (восстановимо) |
| `BuildPlan` | `KnowledgeRuntimeIntegrator._plan` | Время жизни Integrator | ✅ (восстановимо) |
| Integrator singleton | `sys.modules[uploads]._v21_integrator` | Процесс uvicorn | ✅ |
| DomainPipelineBridge | Создаётся per-request | Один запрос | — |
| Event handlers | `get_event_bus()` | Процесс uvicorn | ✅ (восстановимо) |

**Итого**: все накопленные данные (Revision, Projection, Digest) теряются при рестарте.

---

## 9. Какие тесты покрывают startup/runtime lifecycle?

**Никаких.** В репозитории нет тестов:
- `test_startup*` — нет
- `test_bootstrap*` — нет
- `test_lifecycle*` — есть `deal_lifecycle`, но это про бизнес-логику, не про runtime
- `test_recovery*` — нет

Единственный косвенный тест — `test_v2_1_5_integrator.py`, который проверяет `KnowledgeRuntimeIntegrator.integrate()` изолированно, без startup/lifecycle контекста.

---

## 10. Какие минимальные изменения?

### Текущий startup

```
uvicorn start
    ↓
lifespan()
    ├── DB health check
    ├── event handlers
    └── health check
    ↓
request → uploads.py
    ↓
lazy init integrator (Memory)
```

### Целевой startup

```
uvicorn start
    ↓
lifespan()
    ├── DB health check
    ├── event handlers
    ├── init KnowledgeRuntimeIntegrator(PostgreSQL)  ← НОВОЕ
    │       ├── PostgreSQLKnowledgeRevisionRepository
    │       └── PostgreSQLProjectionStore
    └── health check
    ↓
    Runtime ready — QueryEngine доступен без документа
```

### Файлы для изменения

| Файл | Изменение | Объём |
|------|-----------|:-----:|
| `integrator.py` | Добавить `dsn` параметр в `__init__`, выбор реализации | ~10 строк |
| `composition_root.py` | Раскомментировать PostgreSQL store + PostgreSQL strategy | ~20 строк |
| `configuration.py` | Добавить DSN в AdapterConfiguration (если нет) | ~3 строки |
| `backend/main.py` | Добавить создание Integrator в lifespan | ~15 строк |
| `uploads.py` | Убрать lazy init singleton, брать готовый из lifespan | ~10 строк |

**Оценка**: ~60 строк кода, 5 файлов. Без изменения Domain, Query, Projection, Materialization.

---

## План по фазам

### Phase 1 — DI wiring (≈ 40 строк)
- `KnowledgeRuntimeIntegrator.__init__()` принимает опциональный `dsn`
- При наличии dsn создаёт `PostgreSQLKnowledgeRevisionRepository` и `PostgreSQLProjectionStore`
- При отсутствии — Memory (обратная совместимость)

### Phase 2 — Startup hook (≈ 20 строк)
- `backend/main.py lifespan()` создаёт Integrator с DSN из settings
- Сохраняет в `app.state` или через singleton
- Health endpoint отражает `runtime_ready`

### Phase 3 — Lazy init cleanup (≈ 10 строк)
- `uploads.py` убирает lazy init, получает Integrator из lifespan/app.state
- Если Integrator не готов — 503 Service Unavailable

### Phase 4 — Тесты (≈ 100 строк)
- `test_v2_3_runtime_bootstrap.py`: создание Integrator с PostgreSQL
- Проверка: после init в store пусто, repository подключён
- Проверка: materialization пишет в PostgreSQL, QueryEngine читает из PostgreSQL
- Проверка: второй запуск видит те же данные
