# Phase 5B — AI Audit Boundary

**Дата:** 2026-06-16
**Статус:** ❄️ **Boundary Freeze** (до реализации)
**Версия:** 1.0.0

---

## 1. Fundamental Invariant

```
AIAudit(report) → AuditResult
```

**AIAudit не имеет права:**
- Менять report
- Менять register
- Менять assignment
- Менять ledger
- Блокировать подпись

**AIAudit может только:**
- Создавать замечания (findings)
- Формировать score/risk
- Предлагать пересчёт (рекомендация)
- Добавлять evidence (цитаты НК РФ)

---

## 2. Архитектурная позиция

```
Report Generator
     │
     ▼
  Draft Report (immutable input)
     │
     ▼
┌─────────────────────────────────────┐
│        AI Audit Layer               │
│                                     │
│  Formal Pass  → Logical Pass →      │
│  Cross-Check  → Final Score         │
│                                     │
│  Output: AuditResult (read-only)    │
└─────────────────────────────────────┘
     │
     ▼
  Accountant Review (human decision)
     │
     ▼
  Signed Report
```

**Ключ:** AI читает report, но НЕ пишет в него.

---

## 3. Контракт AuditResult

```python
@dataclass(frozen=True)
class AuditFinding:
    finding_id: str
    severity: str          # critical | warning | info
    category: str          # formal | logical | contextual | cross_check
    field_path: str        # путь к ячейке в отчёте (раздел.поле)
    description: str       # описание на русском
    evidence: str | None   # ссылка на НК РФ / статью
    suggested_action: str  # "verify", "recalculate", "exclude", "none"

@dataclass(frozen=True)
class AuditResult:
    report_id: str
    audit_model_version: str
    risk_score: float      # 0.0 (без риска) — 1.0 (критично)
    findings: list[AuditFinding]
    recommendations: list[str]
    approved: bool          # True = прошло все проверки
    created_at: datetime
```

---

## 4. Audit Passes

### 4.1 Formal Pass

Проверки:
- Контрольные соотношения (стр. 010 = стр. 020 + стр. 030)
- Формат полей (ИНН = 10/12 цифр, КПП = 9 цифр)
- Σ дебет = Σ кредит (если применимо)
- period_from ≤ period_to

### 4.2 Logical Pass

Проверки:
- Аномалии: сумма налога < 0
- Выбросы: доход > 3σ от среднего по компании
- Скачки: доход квартала отличается >50% от предыдущего

### 4.3 Contextual Pass

Проверки:
- Нетипичные расходы для режима (УСН + НДС = conflict)
- Соответствие tax_regime форме отчёта
- Незаполненные обязательные поля

### 4.4 Cross-Check Pass

Проверки:
- Ledger.total_income ≈ KUDIR_INCOME.total (допуск 0.5%)
- НДС к уплате ≈ VAT_SALES — VAT_PURCHASE
- Доходы по отчёту = доходы по ledger (с учётом excluded)

---

## 5. AI Audit Replay (уточнённый контракт)

```
AIAuditReplay.run(report, audit_model_version) → AuditResultVersion
```

**AIAuditReplay может:**
- Перезапустить аудит с новой моделью
- Создать новый AuditResultVersion

**AIAuditReplay НЕ может:**
- Создать новый report
- Создать новый register
- Создать новый assignment
- Изменить ledger

### Результат

```
AuditResultVersion
  ├── audit_result_id
  ├── report_id              (тот же самый, не новый)
  ├── audit_model_version    (новая версия модели)
  ├── risk_score
  ├── findings[]
  ├── recommendations[]
  ├── created_at
  └── supersedes             (предыдущая версия AuditResult)
```

### Пример

```
До replay:
  Report v1 (DRAFT)
  AuditResult v1 (model=2026.06.01, risk=0.3, 2 findings)

Новая модель AI (2026.07.01):
  AIAuditReplay(report_v1, model=2026.07.01)

После replay:
  Report v1 (DRAFT) ← не тронут
  AuditResult v1 (model=2026.06.01, superseded=true)
  AuditResult v2 (model=2026.07.01, supersedes=v1, risk=0.1, 0 findings)
```

**Invariant:** AIAuditReplay никогда не создаёт новый report, register, или assignment.

---

## 6. AI never approves

**Жёсткое правило:** AI не может перевести report в статус `accountant_approved`.

| Статус | Кто устанавливает |
|--------|------------------|
| `draft` | Generator |
| `validated` | Validation check |
| `ai_reviewed` | AI Audit (завершил проверку) |
| `accountant_approved` | **Только человек** |
| `signed` | Подпись ЭЦП (Phase 6) |

AI может:
- Поставить `risk_score = 0.0` (нет замечаний)
- Поставить `approved = true` (прошёл все AI проверки)
- Дать рекомендацию «можно подписывать»

AI **не может**:
- Установить `status = accountant_approved`
- Установить `status = signed`
- Заблокировать accountant_approved (accountant может подписать даже с risk=1.0)

---

## 7. Risk Score

```python
risk_score = Σ(weight(severity) × confidence(category)) / Σ max_weight

severity_weights = {
    "critical": 1.0,    # Ошибка в контрольном соотношении
    "warning":  0.5,    # Аномалия, требует внимания
    "info":     0.1,    # Информационное замечание
}
```

Пороги:
- `risk_score < 0.2` → зелёный (без замечаний)
- `risk_score 0.2–0.5` → жёлтый (рекомендована проверка)
- `risk_score > 0.5` → красный (обязательна проверка)

---

## 8. Invariants

| # | Инвариант |
|---|-----------|
| 1 | AIAudit(report) → AuditResult. Никогда не меняет report. |
| 2 | AI Read-Only: audit читает report, register, но не пишет. |
| 3 | AI не может установить статус `accountant_approved`. |
| 4 | AI Replay = новый AuditResult, не новый report. |
| 5 | Accountant может подписать report с любым risk_score. |
| 6 | AuditResult версионирован (audit_model_version). |
| 7 | Formal Pass не использует AI — только математика. |
| 8 | Risk score всегда объясним: каждый finding имеет severity + category. |

---

## 9. Разрешённые и запрещённые входы

### Разрешено читать

| Сущность | Для чего |
|----------|----------|
| `report` | Основной объект аудита |
| `tax_register` | Cross-check: ledger vs register |
| `ledger_entry` | Cross-check: totals |
| `company.tax_regime` | Contextual: режим vs отчёт |
| `ReportTemplateVersion` | Formal: проверка актуальности шаблона |

### Запрещено читать

| Сущность | Причина |
|----------|---------|
| `accounting_event` | Нарушает Layer Isolation |
| `accounting_decision` | Решение уже отражено |
| `document` | Не должно влиять на аудит отчёта |
| `bank_transaction` | Уровень ниже accounting |

---

## 10. Что входит в Phase 5B

| Модуль | Описание |
|--------|----------|
| Audit Contract | AuditResult, AuditFinding, severity |
| Formal Validation | Контрольные соотношения, форматы |
| Logical Pass | Аномалии, выбросы, скачки |
| Contextual Pass | Режимные проверки |
| AI Integration | Запуск модели, разбор результата |
| Multi-pass Orchestrator | 2 независимых AI прохода |

## 11. Что НЕ входит в Phase 5B

| Компонент | Фаза |
|-----------|------|
| AI обучение / дообучение | Вне scope |
| LLM fine-tuning | Вне scope |
| Автоматическое исправление отчёта | Запрещено архитектурой |
| Reconciliation (ledger ↔ bank ↔ tax) | 6 |
| Dashboard / UI | 7 |

---

## 12. Доказательство корректности

### Почему AI не может исправлять отчёт?

1. **Юридическая ответственность**: отчёт подписывает человек (ст. 120 НК РФ).
2. **Галлюцинации**: AI может предложить неверную корректировку → штраф.
3. **Аудит vs Исправление**: если AI исправляет, кто аудирует AI?
4. **Traceability**: каждое исправление должно быть объяснимо человеку.

### Почему AI не может блокировать подпись?

1. **Бизнес-критичность**: компании нужно сдать отчёт вовремя.
2. **AI ошибка**: false positive блокирует сдачу → пеня.
3. **Accountant — ответственное лицо**: решение за человеком.
