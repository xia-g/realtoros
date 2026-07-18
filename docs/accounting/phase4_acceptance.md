# Phase 4 — Tax Assignment + Registers Acceptance Criteria

**Дата:** 2026-06-15
**Статус:** План

---

## 1. Functional

### 1.1. Ledger → Assignment

```
ledger_line
  → TaxAssignmentEngine.assign()
  → TaxAssignment (is_current=true)
```

**Критерий:**
- [ ] Каждая ledger_line получает ровно одно assignment
- [ ] Assignment содержит tax_register_type, tax_treatment, reason_code
- [ ] excluded линии имеют reason_code
- [ ] replay создаёт новые assignment, старые superseded

### 1.2. Assignment → Register

```
TaxAssignment[]
  → TaxRegister.generate()
  → TaxRegisterEntry[]
```

**Критерий:**
- [ ] Каждый assignment порождает register entry
- [ ] excluded assignment → не попадает в register (или попадает в EXCLUDED)
- [ ] Register immutable: новая версия при replay
- [ ] Σ register entries = Σ assigned amounts (без excluded)

### 1.3. Tax Replay

```
TaxReplay.recalculate(tax_policy_version):
  1. Load all ledger_line for period
  2. Assign each line
  3. Generate register
  4. Old register stays (immutable)
```

**Критерий:**
- [ ] Ledger не меняется ни при каких условиях
- [ ] Posting не меняется
- [ ] Старые assignment superseded (is_current=false)
- [ ] Новый register версионирован

### 1.4. Period Mapping

```
Many accounting periods (monthly)
  → one tax period (quarterly)
```

**Критерий:**
- [ ] Tax period ≠ Accounting period
- [ ] Tax period = агрегация accounting periods
- [ ] Accounting period CLOSED → можно закрыть tax period
- [ ] Tax period CLOSED → replay невозможен

---

## 2. Performance

| Метрика | Цель |
|---------|------|
| Assignment throughput | > 1,000 lines/sec |
| Register generation | < 1 sec per 10k entries |
| Tax replay P95 | < 5 sec per 100k lines |

---

## 3. Reliability

| Требование | Критерий |
|-----------|----------|
| Idempotent assignment | Повторный assign даёт тот же register_type |
| Idempotent replay | Двойной replay → 1 активный assignment |
| Determinism | Same ledger + same policy → same register |
| No ledger mutation | ledger_entry.created_at не меняется |

---

## 4. E2E сценарий

```
1. Create posting through full pipeline (event → decision → ledger_entry + ledger_line)
2. TaxAssignmentEngine.assign() for each line
3. Verify: each line has exactly 1 active assignment
4. TaxRegister.generate()
5. Verify: register entries = assigned amounts
6. TaxReplay with new policy version
7. Verify: new assignments created, old superseded
8. Verify: ledger unchanged
9. Verify: register has 2 versions (old + new)
```

---

## 5. Что НЕ входит в Phase 4

| Компонент | Фаза |
|-----------|------|
| Report generation | 5 |
| AI Audit | 5 |
| Tax declarations (УСН, НДС) | 5 |
| Reconciliation | 6 |
| UI | 7 |
