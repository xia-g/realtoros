# Chart of Accounts — Real Estate OS

**Дата:** 2026-06-15
**Версия:** 1.0.0 (минимальный набор для Phase 3)

---

## План счетов

| Код | Наименование | Тип | Родитель |
|-----|-------------|-----|----------|
| 01 | Основные средства | asset | — |
| 02 | Амортизация ОС | asset | — |
| 08 | Вложения во внеоборотные активы | asset | — |
| 10 | Материалы | asset | — |
| 19 | НДС по приобретённым ценностям | asset | — |
| 20 | Основное производство | asset | — |
| 26 | Общехозяйственные расходы | expense | — |
| 44 | Расходы на продажу | expense | — |
| 50 | Касса | asset | — |
| 51 | Расчётные счета | asset | — |
| 60 | Расчёты с поставщиками | liability | — |
| 62 | Расчёты с покупателями | asset | — |
| 68 | Расчёты по налогам и сборам | liability | — |
| 69 | Расчёты по соц. страхованию | liability | — |
| 70 | Расчёты с персоналом | liability | — |
| 71 | Расчёты с подотчётными лицами | asset | — |
| 76 | Расчёты с разными дебиторами/кредиторами | asset | — |
| 90 | Продажи | income | — |
| 90.01 | Выручка | income | 90 |
| 90.02 | Себестоимость продаж | expense | 90 |
| 90.03 | НДС | expense | 90 |
| 90.09 | Прибыль/убыток от продаж | income | 90 |
| 91 | Прочие доходы и расходы | income | — |
| 99 | Прибыли и убытки | income | — |

---

## Posting Rules → Accounts mapping

| Rule | Event types | Дебет | Кредит |
|------|-------------|-------|--------|
| `sale_to_revenue` | sale | 62 (покупатели), 90.03 (НДС) | 90.01 (выручка), 68 (НДС) |
| `client_payment` | client_payment, bank_inflow | 51 (расчётный счёт) | 62 (покупатели) |
| `expense_payment` | purchase, agent_commission | 44 (расходы на продажу) | 60 (поставщики) |
| `bank_transfer` | bank_outflow | 60 (поставщики) | 51 (расчётный счёт) |
| `manual_adjustment` | (catch-all) | 76 (прочие) | 76 (прочие) |

---

## Double Entry Examples

### Sale 150 000 RUB (4 explicit ledger_line)

Each line is an individual `ledger_line` record — no compound entries:

```
 ledger_line #1  │ Дт 62  (Расчёты с покупателями)   150 000
 ledger_line #2  │ Кт 90.01 (Выручка)                 150 000
 ledger_line #3  │ Дт 90.03 (НДС)                     30 000
 ledger_line #4  │ Кт 68  (НДС к уплате)              30 000
                                                  ─────────
Debit:  180 000 │ Credit: 180 000 ✅
```

### Purchase 75 000 RUB (2 explicit ledger_line)

```
 ledger_line #1  │ Дт 44  (Расходы на продажу)        75 000
 ledger_line #2  │ Кт 60  (Расчёты с поставщиками)    75 000
                                                  ─────────
Debit:   75 000 │ Credit:  75 000 ✅
```

---

## Future Invariants (Phase 4 — Tax Registers)

### 5. Every ledger_line → tax register

```
Every ledger_line
belongs to exactly one tax register
or explicitly excluded
```

Запрещено состояние: `ledger exists, tax state unknown`.

Это означает:
- Каждая проводка маппится в конкретный налоговый регистр (КУДиР, НДС, книга доходов/расходов)
- Если линия не налоговая — явный флаг `excluded_from_tax`
- При закрытии периода все линии должны иметь resolved tax state

**Реализация:** таблица `tax_register_line` или колонка `tax_register_id` в `ledger_line` (Phase 4).
**Контроль:** `NOT NULL` или `CHECK (tax_register_id IS NOT NULL OR excluded_from_tax = true)`.

### Current invariants

1. **Σ debit = Σ credit** — double entry
2. **Every ledger_line belongs to exactly one tax period** (period_id NOT NULL)
3. **manual_adjustment requires REVIEW_REQUIRED + reason_code**
4. **No self-reversal** (reversed_entry_id != id)
5. **[Phase 4] Every ledger_line → exactly one tax register or explicitly excluded**
