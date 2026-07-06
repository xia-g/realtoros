# Accounting Roadmap (Consolidated)

**Последнее обновление:** 2026-06-16

---

## Phase 1 — Accounting Core ✅

**Статус:** завершено, freeze активен

**Результат:**
- Accounting Event Journal (9 таблиц, 11 enums, 28 индексов)
- Snapshot (recognition_snapshot)
- Decision (accounting_decision + decision_explanation)
- Replay (ReplayService.recalculate())
- Explainability (rule_code + weight + message + payload)
- Versioning (version, superseded_by, superseded_reason, is_current)

---

## Phase 2 — Recognition + Decision Engine ✅

**Статус:** завершено

**Результат:**
- Queue / Orchestration (event_dispatcher, job_scheduler, retry_policy, dead_letter)
- Workers (recognition, decision, replay)
- Rule Runtime (4 rules: has_supporting_document, expense_allowed_for_usn, bank_movement_confirmed, amount_threshold)
- Replay (ReplayService — immutable snapshot, versioned decision)
- API (10 endpoints: events, decisions, explanations, batches, replay, DLQ, metrics)
- Observability (metrics collector, trace_id, structured audit)
- E2E (10-step pipeline test)

---

## Phase 2.5 — Production Hardening ✅

**Статус:** завершено

**Результат:**
- Reliability (32/32 тестов: restart, dedup, storm, DLQ)
- Performance (Decision P95=35ms, Replay P95=43ms, Insert 7k evt/s)
- Runbooks (5: replay, reprocess, DLQ cleanup, backfill, rules rollout)
- Chaos (8 failure scenarios, risk matrix)
- Release readiness (checklist, rollback, alerts, ownership)

**Ограничения до production:**
- добавить auth middleware
- внедрить worker pool (concurrent)
- внедрить внешнюю очередь (RabbitMQ / NATS)

---

## Phase 3 — Ledger (Double Entry) ✅

**Статус:** завершено, freeze активен

**Scope:**
- chart_of_accounts — план счетов
- ledger_entry — заголовок проводки
- ledger_line — проводка (дебет/кредит)
- posting_engine — движок разноски
- posting_rules — правила корреспонденции
- posting_replay — пересчёт проводок
- period_lock — блокировка закрытых периодов

**Инвариант:**
```
Ledger = f(Decision, PostingRulesVersion)
```

**Результат:** двойная запись (дебет = кредит).

---

## Phase 4 — Tax Registers ✅

**Статус:** завершено, freeze активен

**Scope:**
- Tax Policy (3 режима: USN_D, USN_DR, GENERAL)
- Tax Assignment Engine (ledger_line → tax_register_type)
- Tax Register (KUDIR_INCOME, KUDIR_EXPENSE, VAT_SALES, VAT_PURCHASE, GENERAL_INCOME, GENERAL_EXPENSE, EXCLUDED)
- Tax Replay (не меняет ledger)
- Period Management (open/close tax period)

**Инвариант:**
```
Tax = f(Ledger, TaxPolicyVersion)
```

**Результат:** налоговая база в разрезе регистров.

---

## Phase 5A — Reporting Engine

**Цель:** Генерация регламентированной отчётности из TaxRegister.

**Формула:**
```
Report = f(TaxRegister, ReportTemplateVersion)
```

### 5A.1 Report Template Provider
- загрузка официальных шаблонов (nalog.ru, minfin.ru)
- lifecycle: DISCOVERED → FETCHED → VALIDATED → ACTIVE → DEPRECATED → ARCHIVED
- один ACTIVE на template_id, DEPRECATED доступен для replay
- checksum, schema_version, origin
- immutable: нельзя редактировать вручную

### 5A.2 Report Generator
- `generate(tax_register, template_version) → report`
- report — materialized projection (можно удалить и собрать заново)
- обязательная воспроизводимость
- поддержка: USN, VAT_3, 6NDFL, бухгалтерская, ПСН

### 5A.3 Report Versioning
- report_v1 → report_v2 (correction)
- связи: template_version, register_version, policy_version, generated_at

### 5A.4 Report Cell Identity
- report_cell_id, cell_code, value, source_hash
- каждая ячейка воспроизводима (source_hash доказывает)

### 5A.5 Explainability
- report_cell → register_entry → assignment → ledger_line → posting → decision → explanation
- каждая цифра объяснима (≤ 10 переходов)
- SLA: P95 < 500 ms на ячейку
- кэш — только ускорение, не источник истины

### 5A.6 SubmittedReport
- submission_id ≠ report_id
- Submission не владеет отчётом — только transport metadata
- transport_payload_hash, external_receipt, external_status

### 5A.7 API
- CRUD для черновиков
- GET /reports, POST /reports/generate, POST /reports/{id}/validate

### 5A.8 E2E
- template → report → validation → explainability → submission
- register_v1 ≠ register_v2 → report_v1 ≠ report_v2
- report deletion → rebuild → идентичный report (materialized projection)

**Инварианты:**
- `Report = f(TaxRegister, ReportTemplateVersion)`
- Template — внешний артефакт
- Report — сгенерированный артефакт (не хранит код/формулы)
- SubmittedReport содержит template_version, policy_version, register_version, generated_at

**Документы:**
- `docs/accounting/reporting_boundary.md` v3 (materialized projection, template lifecycle, submitted identity)
- `docs/adr/ADR-015-report-is-generated-artifact.md`

---

## Phase 5B — AI Audit

**Цель:** Независимая AI-верификация отчёта.

**Инвариант:**
```
AIAudit(report) → AuditResult
```
AI не меняет report.

### Проверки

| Pass | Что проверяет |
|------|--------------|
| Formal | Контрольные соотношения, форматы полей |
| Logical | Аномалии, выбросы, скачки >50% |
| Contextual | Режим vs форма, нетипичные расходы |
| Cross-Check | Ledger vs Register vs Report |

### AuditResult

| Поле | Описание |
|------|----------|
| `report_id` | Какой отчёт проверен |
| `audit_model_version` | Версия модели AI |
| `risk_score` | 0.0–1.0 |
| `findings[]` | Замечания с severity |
| `recommendations[]` | Рекомендации |

### Ключевые правила
- **AI не может исправлять отчёт** (read-only)
- **AI не может блокировать подпись** (accountant решает)
- **AI Replay** → новый AuditResult, не новый Report
- **Multi-pass**: минимум 2 независимых AI прохода

**Документы:**
- `docs/accounting/report_ai_boundary.md`

---

## Phase 6 — Signing + Reconciliation

**Цель:** Юридически значимая подпись и сверка данных.

### 6.1 ЭЦП / Signing
- Подписание отчёта электронной подписью
- Поддержка: КЭП, НЭП, простая ЭП
- Интеграция с УЦ (удостоверяющий центр)

### 6.2 Reconciliation
- Ledger ↔ Bank (выверка банковских данных)
- Ledger ↔ Tax Register (налоговая база)
- Tax Register ↔ Report (цифры отчёта)
- Report ↔ Submitted (что отправили = что подписали)

### 6.3 Status Machine
- `signed` → `submitted` → `accepted` / `rejected`
- rejected → correction → новая версия отчёта

---

## Phase 7 — Submission + UI

**Цель:** Отправка отчётности в ФНС и бухгалтерская панель.

### 7.1 Submission
- Транспортный слой: ТКС, СБИС, Диадок
- SubmittedReport: квитанция, дата, статус ФНС
- Повторная отправка при ошибке

### 7.2 UI
- Бухгалтерская панель
- Просмотр отчётов + версий
- Объяснения ячеек (explainability chain)
- AI Audit визуализация
- Replay: кнопка «пересчитать»
- Закрытие периода
- Reconciliation dashboard
