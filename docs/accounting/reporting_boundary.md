# Phase 5 — Reporting Boundary

**Дата:** 2026-06-16
**Статус:** ❄️ **Boundary Freeze** (до реализации)
**Версия:** 3.0.0

---

## 1. Fundamental Formula

```
Report = f(TaxRegister, ReportTemplateVersion)
```

NOT:

```
Report = f(Ledger)
Report = f(TaxAssignment)
Report = f(Decision)
Report = f(Event)
```

---

## 2. Layer Map

```
Template           external artifact (утверждённая форма)
                     │
Report             materialized projection (пересобираемый слепок)
                     │
Audit              independent interpretation (не меняет report)
                     │
Submission         transport artifact (не владеет отчётом)
```

### Семантика слоёв

| Слой | Тип | Можно менять | Нельзя |
|------|-----|-------------|--------|
| Template | external | обновлять версию | редактировать вручную |
| Report | materialized | удалить и собрать заново | править после signing |
| Audit | independent | перезапустить | менять report |
| Submission | transport | повторно отправить | владеть отчётом / копировать register |

---

## 3. Архитектурный поток

```
Ledger
  │
  ▼
Tax Assignment Engine (Phase 4)
  │
  ▼
Tax Register (Phase 4)
  │
  ▼
Report Template (официальный шаблон ФНС)
  │
  ▼
Report Generator (Phase 5A)
  │
  ▼
Draft Report — materialized projection
  │
  ├── Validation (формальные проверки)
  │
  ▼
AI Audit (Phase 5B) — ТОЛЬКО замечания
  │
  ▼
Accountant Review
  │
  ▼
Signed Report (Phase 6)
  │
  ▼
Submission (Phase 7) — транспорт, не владелец
```

---

## 4. Что такое Template

**Template** — внешний артефакт. Официальный шаблон регламентированной отчётности.

```python
@dataclass(frozen=True)
class ReportTemplateVersion:
    template_id: str          # USN_DECLARATION, VAT_3, 6NDFL
    version: str              # "2026.01"
    status: str               # lifecycle state
    effective_from: date
    effective_to: date | None
    checksum: str             # SHA256 всего шаблона
    schema_version: str       # Версия формата (XSD версия)
    origin: str               # "nalog.ru", "minfin.ru"
    locale: str               # "ru_RU"
    fields: JSONSchema        # Описание полей
    formulas: ExpressionTree  # Вычислимые поля
    control_ratios: list[str] # Контрольные соотношения
```

### Template Lifecycle

```
DISCOVERED → FETCHED → VALIDATED → ACTIVE → DEPRECATED → ARCHIVED
```

| Состояние | Описание |
|-----------|----------|
| `DISCOVERED` | Шаблон найден в источнике, ещё не загружен |
| `FETCHED` | Содержимое загружено, checksum проверен |
| `VALIDATED` | Schema, контрольные соотношения, поля — всё корректно |
| `ACTIVE` | Используется для генерации новых отчётов. **Только один ACTIVE на template_id** |
| `DEPRECATED` | Не используется для новых отчётов. **Доступен для replay** (старые отчёты воспроизводимы) |
| `ARCHIVED` | Запрещён для любых генераций. Историческая справка |

**Правила:**
- Один ACTIVE на template_id (последняя утверждённая форма)
- DEPRECATED хранится для replay: `generate(tax_register, template_version=deprecated)` всё ещё работает
- ARCHIVED нельзя использовать для генерации — только для чтения
- Report всегда знает `template_version`, по которой сгенерирован
- При ACTIVE → DEPRECATED: существующие отчёты НЕ пересчитываются
- При ACTIVE → DEPRECATED → ACTIVE (rollback): новый ACTIVE = та же версия, отчёты воспроизводимы

### Контракт ReportTemplateProvider

```python
class ReportTemplateProvider:
    """Источник: официальные XML/XSD формы регламентированных отчётов."""

    async def fetch(template_id: str, version: str | None = None)
        → ReportTemplateVersion

    async def validate(template: ReportTemplateVersion)
        → ValidationResult

    async def activate(template_id: str, version: str)
        → None
        # Делает версию ACTIVE. Предыдущая ACTIVE → DEPRECATED.

    async def archive(template_id: str, version: str)
        → None
        # DEPRECATED → ARCHIVED. Запрещён для генерации.

    async def list(template_id: str | None = None)
        → list[ReportTemplateVersion]
```

**Требования:**
- `effective_from` / `effective_to` — автоматическая смена версии
- `checksum` — защита от подмены
- `origin` — отслеживание источника
- **Нельзя редактировать шаблон вручную** — только загрузка новой версии

---

## 5. Что такое Report

**Report** — **materialized projection**. Заполненный шаблон данными из TaxRegister.

НЕ source of truth. Источник истины — TaxRegister + Template.

**Разрешено:** удалить report и собрать заново (из register + template).

```
Report
  ├── report_id
  ├── report_version
  ├── template_version     ← ReportTemplateVersion (конкретная версия шаблона)
  ├── register_version     ← TaxRegister (конкретная версия)
  ├── register_id
  ├── tax_policy_version   ← TaxPolicyVersion (использованная при assignment)
  ├── generated_at
  ├── cells[]              ← заполненные ячейки
  └── status               ← lifecycle
```

### Report Cell Identity

```python
@dataclass(frozen=True)
class ReportCell:
    cell_id: str             # report_version + cell_code (уникальный в рамках версии)
    report_version: str
    cell_code: str           # "section_1.line_010" — код поля в шаблоне
    value: str | float | None
    source_hash: str         # SHA256(template_field_id + register_entry_ids + formula)
```

**Инвариант:** Каждая ячейка воспроизводима. `source_hash` доказывает: одинаковые входы → одинаковое значение.

### SubmittedReport Identity

**Инвариант:** `submitted_report != report`.

Submission не владеет отчётом. Submission — транспортный артефакт.

```
SubmittedReport
  ├── submission_id         # ID транспорта, не ID отчёта
  ├── report_version        # Версия отчёта, который отправлен (ссылка, не копия)
  ├── transport_payload_hash  # SHA256 того, что реально ушло в ФНС
  ├── submitted_at
  ├── external_receipt      # Квитанция от ФНС (входящий номер)
  └── external_status       # accepted | rejected | processing
```

**Submission НЕ содержит:**
- `register` (копию налогового регистра)
- `assignment` (копию назначений)
- `template` (копию шаблона)

Submission хранит только метаданные транспорта. Отчёт остаётся в системе.

### SubmitReport (обязательные ссылки)

| Поле | Источник |
|------|----------|
| `report_template_version` | Версия шаблона, по которому сгенерирован |
| `tax_policy_version` | Версия налоговой политики на момент расчёта |
| `register_version` | Конкретная версия регистра |
| `generated_at` | Дата/время генерации |

---

## 6. Report Versioning

```
report_v1 (original)
report_v2 (correction)
report_v3 (recalculation)
```

**Инвариант:** исправление отчёта = новая версия. Старая остаётся.

### Версионные связи

```
report
  ├── template_version    (какая форма)
  ├── register_version    (какой регистр)
  ├── tax_policy_version  (какая политика)
  └── audit_version       (какой аудит)
```

### Replay

```
Replay отчёта = generate(tax_register, template_version)
```

- Не трогает ledger
- Не трогает tax assignment
- Не трогает tax register
- Создаёт новую версию отчёта (если шаблон/регистр изменился)

---

## 7. Отчёт — materialized projection, не source of truth

Report — это **пересобираемый слепок**, не источник истины.

| Свойство | Report | TaxRegister |
|----------|--------|-------------|
| Source of truth | ❌ Нет | ✅ Да |
| Можно удалить | ✅ Да, собрать заново | ❌ Нет (immutable) |
| Можно пересчитать | ✅ generate(...) | ❌ replay создаёт новую версию |
| Хранит код/формулы | ❌ Нет | ❌ Нет |
| Хранит данные | ✅ Значения ячеек | ✅ Проводки |

**Почему:**
- Источник истины для налоговых данных — TaxRegister
- Источник истины для формы — ReportTemplate
- Report — пересечение этих двух источников в конкретный момент времени
- Если report удалён: `generate(tax_register, template_version)` восстановит идентичный

---

## 8. Report Determinism

**Инвариант:** генерация отчёта детерминирована.

```
generate(register_version, template_version) ≡ same report_hash
```

Одинаковые входы → одинаковый report_hash.

### Что входит в report_hash

```python
report_hash = SHA256(
    register_version +
    template_version +
    sorted(cells, key=lambda c: c.cell_code)
)
```

Где `cells` — не PDF/XML/Excel, а структурированные данные:
- cell_code
- значение
- source_hash

### Что гарантирует детерминизм

| Условие | Следствие |
|---------|-----------|
| Один register_version + один template_version | Один report_hash |
| 100 раз вызвать generate() | 100 раз одинаковый report_hash |
| Удалить report и перегенерировать | Тот же report_hash |
| Разные даты/времена генерации | Не влияют на hash |

### Что НЕ влияет на hash

- generated_at (метаданные, не данные)
- created_by (кто запустил)
- trace_id (идентификатор сессии)
- audit_result (аудит — отдельный слой)
- submission_status (транспорт — отдельный слой)

---

## 9. Report Storage vs Rendering

**Инвариант:** `report_rendering ≠ report_storage`.

### Что хранить (storage)

```
Report (materialized projection)
  ├── structure        (поля, разделы, иерархия — по template)
  ├── values[]         (cell_code → значение)
  ├── source_hash[]    (каждая ячейка: SHA256 входов)
  └── metadata         (report_version, template_version, register_version,
                       policy_version, generated_at, status)
```

### Что генерируется на лету (rendering)

```
PDF   (для печати / подписи)
XLSX  (для анализа / сверки)
XML   (для отправки в ФНС)
HTML  (для предпросмотра)
JSON  (для API)
```

**Правило:** rendering всегда производный. PDF/XLSX/XML/HTML/JSON — это view, не data.

### Последствия

| Действие | Storage | Rendering |
|----------|---------|-----------|
| Сгенерировать отчёт | ✅ Создать структуру + values | ✅ Создать PDF (кэш) |
| Изменить template | ❌ Не трогать | ❌ Удалить кэш |
| Удалить rendering | ❌ Не трогать | ✅ Разрешено (пересоздать) |
| Удалить storage | ❌ Потеря данных | ❌ Бессмысленно |
| Пересчитать отчёт | ✅ Новая версия | ✅ Новый rendering |
| Сравнить две версии | ✅ Hash values | ❌ Diff PDF — шум |

**Ключ:** storage всегда можно перерендерить в любой формат.
Rendering никогда не считается source of truth.

---

## 10. Разрешённые входы в Report Generator

| Сущность | Режим |
|----------|-------|
| `tax_register` | Чтение (current + history) |
| `tax_register_entry` | Чтение (детализация сумм) |
| `company.tax_regime` | Чтение (форма отчёта) |
| `company.inn`, `kpp`, `ogrn` | Чтение (реквизиты) |
| `ReportTemplateVersion` | Версия шаблона |
| `tax_period` | Чтение (период отчёта) |

### Запрещённые входы

| Сущность | Причина |
|----------|---------|
| `ledger_entry` | Обход Tax Layer — потеря объяснимости |
| `ledger_line` | Нарушает `Report = f(TaxRegister)` |
| `accounting_event` | Нарушает Layer Isolation |
| `accounting_decision` | Решение уже отражено в регистре |
| `bank_transaction` | Прямая зависимость от банка |
| `document` | Нарушает snapshot-only invariant |

---

## 11. Report Lifecycle

```
DRAFT → VALIDATED → AI_REVIEWED → ACCOUNTANT_APPROVED → SIGNED → SUBMITTED → ACCEPTED / REJECTED
```

| Статус | Описание |
|--------|----------|
| `draft` | Сгенерирован, не проверен |
| `validated` | Прошёл формальные контрольные соотношения |
| `ai_reviewed` | AI проверил, замечания приложены (но не блокирует) |
| `accountant_approved` | Бухгалтер подтвердил |
| `signed` | Подписан ЭЦП (Phase 6) |
| `submitted` | Отправлен в ФНС (Phase 7) |
| `accepted` | Принят налоговым органом |
| `rejected` | Отказ ФНС (требуется корректировка → новая версия) |

**Правило:** AI never approves. Статус `accountant_approved` может установить только человек.

---

## 12. Explainability Chain

```
report_cell (конкретная цифра в отчёте)
  │
  ├── template_field_id    (какое поле шаблона)
  ├── formula_applied      (какая формула: KUDIR_INCOME.total × 0.06)
  ├── source_hash          (доказательство воспроизводимости)
  │
  ▼
register_entry
  │
  ├── register_id → TaxRegister
  ├── register_type (KUDIR_INCOME)
  ├── amount
  │
  ▼
assignment
  │
  ├── assignment_id → TaxAssignment
  ├── register_type
  ├── tax_treatment
  ├── reason_code
  │
  ▼
ledger_line
  │
  ├── account_code (90.01)
  ├── direction (credit)
  ├── amount
  │
  ▼
posting_decision_link
  │
  ├── posting_rule_code
  ├── decision_id
  │
  ▼
accounting_decision
  │
  ├── included
  ├── reason
  │
  ▼
decision_explanation[]
  │
  ├── rule_code
  ├── weight
  └── message
```

**Инвариант:** Каждая цифра в отчёте прослеживается до decision_explanation.
Максимум: 10 переходов (все по PK/FK, без full scans).

### Explainability SLA

| Метрика | Цель |
|---------|------|
| Объяснение одной ячейки P95 | < 500 ms |
| Максимум переходов | 10 (report_cell → decision_explanation) |
| Кэш как источник истины | ❌ Запрещён. Только прямые JOIN по PK/FK |
| Кэш как оптимизация | ✅ Разрешён (не влияет на корректность) |

**Правило:** кэш может ускорять, но не может заменять источник истины.

---

## 13. Invariants

| # | Инвариант |
|---|-----------|
| 1 | `Report = f(TaxRegister, ReportTemplateVersion)` |
| 2 | Template — внешний артефакт (редактируется только через формальную замену) |
| 3 | Report — materialized projection (можно удалить и собрать заново) |
| 4 | Report — НЕ source of truth. Источник = Register + Template. |
| 5 | Audit — независимая интерпретация (не меняет report) |
| 6 | Submission — транспортный артефакт (submission_id ≠ report_id) |
| 7 | Submission не владеет отчётом. Хранит только метаданные транспорта. |
| 8 | Один ACTIVE template на template_id. DEPRECATED доступен для replay. |
| 9 | Report всегда знает template_version, register_version, policy_version. |
| 10 | Новый audit → новый AuditResultVersion, не новый report. |
| 11 | `generate(register_version, template_version)` детерминирован: одинаковые входы → report_hash |
| 12 | `report_rendering ≠ report_storage`. PDF/XLSX/XML — производные артефакты. Storage = structure + values + hashes. |
| 13 | Объяснение ячейки P95 < 500ms, ≤ 10 переходов. |
| 14 | Кэш не является источником истины для explainability. |
| 15 | Два одинаковых Template + одинаковый TaxRegister = одинаковый Report |
| 16 | Report immutable после signing |
| 17 | Исправление отчёта = новая версия. Старая остаётся. |
| 18 | AI не может установить статус `accountant_approved` |
| 19 | Каждая ячейка отчёта имеет source_hash для воспроизводимости |

---

## 14. Acceptance Gates

### Functional

| Gate | Условие |
|------|---------|
| Одна форма → два отчёта → одинаковые значения | `same template + same register → same report cells → same report_hash` |
| Новая форма → новый report → те же регистры | `new template_version → new report, register unchanged` |
| Новый аудит → новый AuditResult → тот же report | `audit re-run → new AuditResultVersion, report_id unchanged` |
| Детерминизм | `generate(rv, tv) × 100 → 100× identical report_hash` |

### Reliability

| Gate | Условие |
|------|---------|
| Template rollback | ACTIVE → DEPRECATED → ACTIVE — отчёты воспроизводимы |
| Audit replay | Повторный запуск AI → новый AuditResult, report не тронут |
| Submission retry | Повторная отправка → новый submission_id, report_version тот же |
| Report deletion + rebuild | `delete report → generate(tax_register, template) → идентичный report_hash` |

---

## 15. Что входит в Phase 5A — Reporting Engine

| Модуль | Описание |
|--------|----------|
| Report Template Provider | Загрузка и версионирование шаблонов (DISCOVERED → ACTIVE → DEPRECATED → ARCHIVED) |
| Report Generator | `generate(tax_register, template) → report` (materialized projection, deterministic) |
| Report Cell Identity | source_hash, cell_code, воспроизводимость |
| Report Validation | Контрольные соотношения, форматы |
| Report Storage | structure + values + hashes (rendering — производный) |
| Report Draft API | CRUD для черновиков |
| Explainability | Цепочка от cell до decision_explanation + SLA P95 < 500ms |
| SubmittedReport | transport metadata, не копия отчёта |
| E2E | template → report → validation → explainability → submission |

## 16. Что входит в Phase 5B — AI Audit

| Модуль | Описание |
|--------|----------|
| AI Audit Contract | AuditResult, findings, risk_score |
| Audit Runner | Запуск AI-модели над отчётом |
| Audit Replay | Повторный запуск → новый AuditResultVersion, report не тронут |
| Formal Checks | Контрольные соотношения, аномалии |
| Contextual Checks | Нетипичные расходы, режимные риски |
| Multi-pass | Минимум 2 независимых AI прохода |

## 17. Что НЕ входит (отложено)

| Компонент | Фаза |
|-----------|------|
| ЭЦП / signing | 6 |
| Отправка в ФНС | 7 |
| Reconciliation (ledger ↔ bank ↔ tax) | 6 |
| UI | 7 |

---

## 18. Связь с Phase 4

```
Phase 4 output:
  TaxRegister (total_amount, register_type, entries, version)

Phase 5A input:
  TaxRegister.current
  ReportTemplateVersion.active

Boundary:
  Phase 4     → produce TaxRegister (source of truth)
  Phase 5A    → consume TaxRegister, produce Report (materialized projection)
  Phase 4 НЕ  → содержит template, report, declaration logic, audit
  Phase 5A НЕ → содержит assignment, register engine, policy
```
