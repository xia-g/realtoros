# ADR-014: Tax Assignment Layer — Separate from Ledger

**Дата:** 2026-06-15
**Статус:** Принято
**Версия:** 1.0.0

---

## Контекст

Phase 3 (Ledger) завершён. Ledger immutable, double-entry, period lock.

Следующий этап — налоги.

Главный вопрос: где хранить привязку проводки к налоговому регистру?

Варианты:
A. Колонка `tax_register_id` в `ledger_line`
B. Отдельный слой TaxAssignment (вне Ledger)
C. Гибрид — колонка + отдельная таблица для истории

---

## Решение

**Вариант B:** Отдельный слой TaxAssignment.

### Формула

```
Tax = f(Ledger, TaxPolicyVersion)
```

NOT:
```
ledger_line.tax_register_id
```

### Аргументы

1. **Ledger immutable**: если налоговая политика меняется, UPDATE ledger_line невозможен. Пришлось бы создавать reversal + новую проводку, что смешивает бухгалтерскую и налоговую логику.

2. **Независимые версии**: posting_rules_version и tax_policy_version меняются независимо. Одна проводка может иметь разные налоговые интерпретации в разное время.

3. **История**: налоговая интерпретация — мнение, факт — проводка. Ledger хранит факты, TaxAssignment хранит мнения.

4. **Replay без шума**: пересчёт налога не должен создавать новые проводки в Ledger. Если `tax_register_id` встроен в `ledger_line`, пересчёт потребует изменения Ledger.

---

## Последствия

### Positive

- Ledger остаётся чистым (account, amount, direction, period)
- Tax replay не трогает Ledger
- Одна проводка → много assignment версий (история)
- TaxPolicyVersion не зависит от PostingRulesVersion

### Negative

- Дополнительный JOIN для ответа на вопрос «какой налог у этой проводки?»
- Нужна синхронизация: нельзя закрыть tax period, пока есть ledger_line без assignment
- Больше сущностей: TaxAssignment, TaxRegister, TaxRegisterEntry

---

## Отклонённые варианты

### Вариант A: tax_register_id в ledger_line

**Отклонено.** Нарушает immutable ledger. UPDATE ledger_line при смене налоговой политики. Невозможно хранить историю налоговых интерпретаций. Ledger перестаёт быть чистым фактом.

### Вариант C: Гибрид (колонка + история)

Колонка `current_tax_register_id` + отдельная таблица для истории изменений.

**Отклонено.** Сложнее, чем чистый Assignment Layer, без дополнительных преимуществ. История assignment уже есть в TaxAssignment (версионирован). Дублирование колонки создаёт риск рассинхронизации.

---

## Связанные ADR

- ADR-013: Ledger Boundary — Input Isolation
- ADR-012: Architecture Freeze V1

---

## Статус

Принято. Архитектурная граница Tax Layer зафиксирована.
