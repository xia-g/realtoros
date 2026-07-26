# Architecture Review: Stream 3 — Business Events (7 пунктов)

**Дата:** 2026-07-24
**Рецензент:** Hermes Agent (автоматизированный architecture review)
**Документ:** `stream-03-business-events/proposal.md` (2520 строк)
**Источники:** proposal.md, Foundation Checkpoint, ADR-001, ADR-016-to-021

---

## 1. ADR-019 — Event sourcing vs append-only log

**Status:** ❌ **Missing**

**Evidence:**
- Foundation Checkpoint (строка 186): `ADR-019 | Event sourcing vs append-only log` — указан как **Pending** для Stream 3.
- Приложение B proposal (строка 2520): `ADR-019: Event sourcing vs append-only log | Создать` — статус «Создать», то есть не создан.
- Существующий файл `ADR-016-to-021-knowledge-runtime.md` содержит ADR-019, но он про **JSONB вместо ORM** в Knowledge Runtime — совершенно другой контекст. ADR-019 занят. ADR про event sourcing **не существует** нигде в docs/adr/.

**Gap:**
Proposal уже принял фундаментальное архитектурное решение — append-only log вместо полного Event Sourcing — но **не оформил его как ADR**. Это критично, потому что:
1. Решение затрагивает все downstream Streams (4–11), которые будут строить свои архитектуры на этом допущении.
2. Без ADR нет документированного сравнения альтернатив (Event Store, Kafka as source of truth, CDC-based approach).
3. Без ADR нет явной фиксации, **какие возможности Event Sourcing сознательно теряются** (восстановление агрегатов исключительно из событий, snapshot-based быстрый recovery, built-in event versioning).
4. Без ADR нет обоснования выбора append-only перед полным Event Sourcing для следующих Streams.

**Recommendation:**
Создать ADR-019 (используя другой номер, так как ADR-019 занят) с обязательным содержанием:
- Рассмотренные альтернативы: Event Store / Kafka как source of truth / CDC-based / Append-only SQL
- Причины отказа от полного Event Sourcing
- Какие преимущества остаются: audit trail, replay, determinism
- Какие возможности теряются: полное восстановление агрегатов из событий, built-in snapshotting
- Последствия для Stream 4 (State), Stream 7 (Simulation), Stream 11 (Explainability)

---

## 2. Replay

**Status:** ⚠️ **Partial**

**Evidence:**
Proposal имеет отдельный раздел 7 «Replay» (строки 786–916) с:
- `ReplayOrchestrator` с `full_replay()` и `partial_replay()` (строки 1625–1684)
- `IEventRepository.replay_by_aggregate()` (строки 849–858)
- `IEventRepository.replay_by_type()` (строки 861–870)
- Требования к детерминизму (строки 896–916)
- Replay в тестовой стратегии (строки 2343–2345, 2383–2422)
- Sequence diagram (строки 2256–2279)

**Gap #1 — Очистка старого состояния:**
Proposal не отвечает на вопрос: replay в **новый** projection (с нуля) или поверх **существующего**? Если поверх существующего — нужно ли очищать старое состояние перед replay? ReplayOrchestrator просто вызывает `apply_fn(event)` в цикле (строка 1662), но не очищает state перед началом. Ожидается, что `apply_fn` сам решает эту проблему. Это ответственность не документирована.

**Gap #2 — Транзакционность replay:**
Replay применяет события в цикле (одно за другим, строки 1660–1664). Нет упоминания:
- replay идёт в одной транзакции или пакетами?
- что происходит при падении посередине replay?
- есть ли checkpointing (частичный replay с сохранением прогресса)?

**Gap #3 — Параллельный replay:**
Нет обсуждения возможности параллельного replay (например, replay разных агрегатов одновременно, или шардированная загрузка одного агрегата).

**Recommendation:**
1. Документировать, что `apply_fn` должен сам обрабатывать очистку (clear state before replay); либо добавить explicit step в ReplayOrchestrator.
2. Добавить раздел про crash recovery при replay — что происходит при падении? Нужен checkpoint (сохранение last_applied_sequence) для возобновления.
3. Рассмотреть batch-based replay для больших объёмов.
4. Явно указать: параллельный replay разных агрегатов — да, параллельный replay одного агрегата — нет.

---

## 3. Event Payload

**Status:** ⚠️ **Partial**

**Evidence:**
- `EventPayload` определён (строки 227–237): `event_type`, `organization_id`, `period`, `data: dict[str, Any]`, `producer`.
- `EventMetadata` отделён от payload (строки 149–163): `source`, `schema_version`, `created_at`, `created_by`.
- Metadata — служебная информация (соглашение соблюдено).
- `producer` находится в EventPayload, а не в metadata. Это несоответствие — `producer` (имя сервиса) это скорее инфраструктурная информация, чем доменные данные.

**Gap #1 — Нет принципа разделения metadata/payload:**
Proposal не формулирует явный принцип: «Metadata — инфраструктурная информация, Payload — только доменные данные». Вместо этого:
- `producer` — инфраструктурное поле, но живёт в Payload
- `source` — инфраструктурное поле, но живёт в Metadata
- Нет чёткой границы, что куда относится

**Gap #2 — `data: dict[str, Any]`:**
Payload.data — типизирован как `dict[str, Any]`. Это потенциальный «JSON со всем подряд». Нет:
- Принципа «никаких transport-specific полей в payload»
- Принципа «никаких ORM/entity ссылок (FK) в payload»
- Документированных правил, что МОЖЕТ и что НЕ МОЖЕТ быть в payload.data
- Референса к тому, как EventType определяет структуру payload (каждое событие имеет свою схему, но это не формализовано)

**Gap #3 — Дублирование:**
`event_type` есть и в `BusinessEvent.event_type`, и в `EventPayload.event_type`. Это избыточность. `organization_id` также дублируется.

**Recommendation:**
1. Убрать `producer` из EventPayload (переместить в EventMetadata или удалить — он дублирует `source`).
2. Убрать дублирование `event_type` и `organization_id` из EventPayload (они уже есть в BusinessEvent).
3. Сформулировать и добавить принцип разделения:
   - **Metadata:** source, schema_version, created_at, created_by, producer (инфраструктура)
   - **Payload (domain data):** только бизнес-поля, специфичные для EventType
4. Добавить правило: никаких FK, ORM-ссылок, transport headers в payload.

---

## 4. Event Versioning

**Status:** ⚠️ **Partial**

**Evidence:**
- Раздел 5 «Event Versioning» (строки 611–711)
- `schema_version` в `EventMetadata` (строка 628)
- `IEventSchemaRegistry` с `get_parser(event_type, schema_version)` (строки 664–688)
- Правила backward-compatible и breaking изменений (строки 635–655)
- Стратегия: сырой payload как JSONB, парсеры на read path (строка 690)

**Gap #1 — Нет разделения event_type_version vs schema_version:**
Proposal использует только `schema_version` для всего:
- Нет `event_type_version` — отдельного поля для версии типа события.
- Если два события одного EventType имеют разные схемы — различаются только значением `schema_version`.
- Но если EventType меняет семантику (например, `accounting.period_closed` теперь включает новые поля) — это не отражено на уровне типа.

**Gap #2 — Нет аргументации:**
Proposal не объясняет, ПОЧЕМУ `schema_version` достаточно и ПОЧЕМУ не нужно `event_type_version`. Это оставляет вопрос открытым для следующих Streams. Foundation Checkpoint (строка 121–122) дефернул риск R5: «Event schema versioning not stress-tested — Stream 3 will implement event_schema_version and versioned parsers». Риск не закрыт — нет аргументации.

**Recommendation:**
1. Добавить явное решение: **schema_version — единый механизм версионирования**. Если решено не вводить `event_type_version` — дать обоснование (простота, достаточность для Compliance, schema_version + EventType комбинация однозначно идентифицирует формат).
2. Если `event_type_version` нужен — ввести его как поле в EventType enum (например, `accounting.period_closed.v2`).
3. Закрыть риск R5 из Foundation Checkpoint явным решением.

---

## 5. Ordering

**Status:** ✅ **Covered** (с одним уточнением)

**Evidence:**
- Раздел 6 «Ordering» (строки 715–782)
- Решение: FIFO per AggregateId, NO global order (строки 720–748)
- `sequence_number` монотонный внутри AggregateId
- `UNIQUE(aggregate_id, sequence_number)` constraint (строка 1793)
- `next_sequence()` = `SELECT MAX + 1` (строка 1270)
- Consumer gap detection pattern (строки 762–782)

**Gap — Конкурентная запись в один Aggregate:**
`next_sequence()` использует `SELECT COALESCE(MAX(sequence_number), 0) + 1`. При конкурентных записях в один Aggregate:
- Два concurrent запроса получат одинаковый `MAX + 1`
- UNIQUE constraint поймает второй INSERT, он упадёт с SequenceGapError
- **Ретрай:** в коде нет механизма retry для этого случая
- **Кто выдаёт:** `EventRepository.next_sequence()` — но если связка sequence_number → aggregate_id неуникальна, retry будет повторять SELECT MAX + 1 снова

Proposal не отвечает на вопросы:
- Кто отвечает за retry при sequence conflict?
- Есть ли retry loop в EventService?
- Какова конвенция: Application Service retry или caller retry?

**Recommendation:**
Добавить в proposal раздел о конкурентной записи:
1. Механизм retry: Application Service retry loop (до 3 попыток) при SequenceGapError.
2. Или: альтернативный подход — PostgreSQL SEQUENCE для sequence_number (но потеря монотонности при ROLLBACK).
3. Явно задокументировать, что при высокой конкурентности на один Aggregate будут retry.

---

## 6. Outbox

**Status:** ⚠️ **Partial**

**Evidence:**
- Раздел 4 «Transactional Outbox» (строки 397–608)
- `FOR UPDATE SKIP LOCKED` при fetch_pending (строка 549, 1350–1352)
- `uq_outbox_event UNIQUE(event_id)` — идемпотентность записи (строка 427, 1841)
- OutboxRecoveryService с `max_retries = 3` (строки 586–598)
- `retry_count` и `last_error` в outbox таблице (строки 423–424, 1837–1838)

**Gap #1 — Несколько экземпляров Publisher:**
`FOR UPDATE SKIP LOCKED` поддерживает конкурентные publisher'ы — каждый берёт свою порцию. Но нет явного утверждения, что Outbox может запускаться в нескольких экземплярах. Нет обсуждения graceful shutdown (что происходит с взятыми, но не обработанными записями при падении publisher'а).

**Gap #2 — Retry backoff:**
OutboxRecoveryService имеет `max_retries = 3`, но **нет backoff** между retry. Если брокер недоступен, publisher будет долбить его без паузы. Нет:
- exponential backoff
- jitter
- max backoff threshold

**Gap #3 — Poison message policy:**
Нет обсуждения, что происходит с событием, которое consistently фейлится (poison message):
- `fetch_failed(max_retries=3)` — после 3 retry событие просто перестаёт выбираться
- Куда оно идёт? Dead letter queue? Вручную? Просто остаётся в outbox навсегда?
- Нет мониторинга stale failed записей

**Gap #4 — Гарантия уникальности публикации:**
`uq_outbox_event` предотвращает INSERT дубликата. Но нет механизма, предотвращающего повторную публикацию после mark_published() если произошёл crash между успешной публикацией в брокер и UPDATE status = 'published'. При восстановлении publisher прочитает событие (если status всё ещё 'pending' или 'failed') и опубликует снова — **at-least-once**, что proposal и декларирует. Но это не задокументировано как intentional trade-off.

**Recommendation:**
1. Добавить **exponential backoff** в OutboxPublisher: `min_backoff=1s, max_backoff=60s, multiplier=2`.
2. Определить **poison message policy**: после N retry — move to DLQ (dead letter queue), alert, manual intervention.
3. Явно задокументировать "multiple publisher instances supported via FOR UPDATE SKIP LOCKED".
4. Явно задокументировать at-least-once trade-off: crash между publish + mark_published → duplicate delivery.

---

## 7. Cross-stream Contracts

**Status:** ⚠️ **Partial**

**Evidence:**
- Раздел 9 «Cross-stream Contracts» (строки 1015–1108)
- Event Backbone через брокер (строки 1019–1032)
- Таблица контрактов для каждого Stream 4–11 (строки 1099–1107)
- Архитектурный инвариант #19: «Event Backbone не зависит от формата payload Consumer'ов» (строка 1145)
- Архитектурный инвариант #20: «Consumer не обязан знать о других Consumer'ах» (строка 1146)

**Gap #1 — Правило не сформулировано явно:**
Нет явного, нерушимого правила: **«Ни один downstream Stream не читает SQL-таблицы Stream 3. Всё взаимодействие — через BusinessEvent / EventEnvelope через брокер»**. Раздел 9 описывает, ЧТО каждый Stream получает, но не формулирует запрет на прямой SQL-доступ.

**Gap #2 — API endpoints могут стать соблазном:**
Stream 3 предоставляет HTTP API: `GET /events?aggregate_id=...`. Это удобно для отладки, но downstream Streams могут начать использовать его как основной источник данных, bypassing Event Backbone. Нет предупреждения об этом.

**Gap #3 — Гарантии контракта документированы, но не тестируемы:**
Контракты в таблице (строки 1099–1107) описывают гарантии (ordered, at-least-once, replay), но нет:
- Contract test'ов, которые downstream Stream может запустить для проверки контракта
- Shared contract interface или abstract test class
- Определения SLA для брокера (latency, throughput)

**Recommendation:**
1. Добавить явное правило в раздел 9 или в Architectural Invariants:
   > **«Downstream Streams НЕ имеют доступа к SQL-таблицам Stream 3. Взаимодействие — исключительно через BusinessEvent, доставленный Event Backbone (брокер). Чтение compliance.business_events напрямую запрещено.»**
2. Добавить рекомендацию downstream Streams: не использовать HTTP API для production consumption.
3. Рассмотреть добавление AbstractConsumerContractTests — базового набора тестов, который проверяет ordering, idempotency, at-least-once для любого consumer.

---

## Итоговая таблица

| # | Пункт | Status | Ключевой gap | Приоритет |
|:-:|:------|:-------|:-------------|:----------|
| 1 | ADR-019 | ❌ Missing | ADR не создан, номер занят | **BLOCKER** |
| 2 | Replay | ⚠️ Partial | Очистка state, crash recovery, batch | High |
| 3 | Event Payload | ⚠️ Partial | Нет принципов, `producer` в payload, дублирование | Medium |
| 4 | Event Versioning | ⚠️ Partial | Нет `event_type_version`, нет аргументации | Medium |
| 5 | Ordering | ✅ Covered | Конкурентная запись — retry не описан | Low |
| 6 | Outbox | ⚠️ Partial | Backoff, poison message, multi-instance docs | High |
| 7 | Cross-stream Contracts | ⚠️ Partial | Нет явного запрета на прямой SQL | High |

**Легенда:** Priority — субъективная оценка влияния на архитектурную целостность.

**Единственный BLOCKER:** ADR-019. Без него решение append-only vs event sourcing не зафиксировано.
