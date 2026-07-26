# ADR-014: Rule Evaluation Trace — структурированное дерево результатов

**Статус:** Draft  
**Дата:** 2026-07-23  
**Контекст:** Epic 3 — Accounting Compliance & Reporting, Stream 2  
**Автор:** Architect (RealtorOS)

---

## Контекст

Пользователь (бухгалтер) должен понимать, **почему** правило не выполнено:

> «Декларация по УСН не готова, потому что период 2026-06 ещё не закрыт»

Для Explainability API (Stream 11) и Dependency Engine (Stream 6) необходимо структурированное дерево результатов оценки, которое:
- Идентифицирует, **какое правило** оценивалось (rule_code, version)
- Показывает, **какие факты** проверены и их статус
- Даёт **человекочитаемое пояснение** для каждого узла
- Соответствует **AST** проверяемого выражения

## Решение

### 1. RuleEvaluationTrace — дерево с идентификацией правила

```python
@dataclass(frozen=True)
class RuleEvaluationTrace:
    # ── Rule identity ──────────────────────────────────────────
    rule_code: RuleCode                # какое правило оценивалось
    version_number: int                # какая версия правила
    effective_from: date               # effective_from версии на момент оценки

    # ── Expression trace ───────────────────────────────────────
    expression_type: Literal["ALL", "ANY", "NOT", "FACT"]
    fact_code: str | None
    status: Literal["confirmed", "missing", "disputed", "skipped"]
    children: tuple["RuleEvaluationTrace", ...] = ()
    detail: str | None = None
```

### 2. Статусы узлов

| Статус | Значение | Пример |
|:-------|:---------|:-------|
| `confirmed` | Факт подтверждён / ALL-все дети true / ANY-хотя бы один true | `revenue_posted ✔` |
| `missing` | Факт не найден / ALL-не все дети true / ANY-ни один не true | `period_closed ✘` |
| `disputed` | Факт существует, но его достоверность под вопросом | `expenses_confirmed ⚠` |
| `skipped` | Узел не оценивался (NOT: ребёнок не оценивался, если факт не нужен) | `NOT(revenue_posted) — skipped` |

### 3. Пример дерева

```
RuleEvaluationTrace
  rule_code="usn_declaration"
  version_number=3
  effective_from=2026-01-01
  expression_type=ALL
  status=missing
  ├── FACT revenue_posted     → status=confirmed  → "Факт revenue_posted подтверждён"
  ├── FACT expenses_confirmed → status=confirmed  → "Расходы подтверждены"
  └── FACT period_closed      → status=missing    → "Период 2026-06 ещё не закрыт"
```

### 4. Связь с AST

Trace — это **результат оценки**, а не AST. Одно и то же AST может дать разные trace в зависимости от состояния бизнес-фактов.

Структура trace **повторяет структуру AST**: для каждого узла ALL/ANY/NOT/FACT в AST создаётся соответствующий узел в trace с вычисленным `status`.

### 5. RuleResult (результат оценки одного правила)

```python
@dataclass(frozen=True)
class RuleResult:
    rule_code: RuleCode
    version_number: int
    status: Literal["passed", "failed", "pending", "error"]
    trace: RuleEvaluationTrace
```

## Обоснование

| Вариант | Минусы |
|:--------|:-------|
| **Только boolean (passed/failed)** | Невозможно объяснить *почему*; пользователь не может исправить проблему |
| **Текстовое сообщение** | Неструктурированно; невозможно анализировать программно; сложно локализовать |
| **Дерево трассировки с идентификацией правила** | Полная прозрачность: какое правило, какая версия, какие факты, какие статусы |

## Последствия

**Positive:**
- Пользователь видит точную причину: «период не закрыт», а не просто «декларация не готова»
- Программный анализ: Dependency Engine (Stream 6) может собирать все missing факты
- Explainability API (Stream 11) использует trace напрямую для LLM-рендеринга
- rule_code + version_number + effective_from однозначно идентифицируют применённое правило

**Negative:**
- Размер trace может быть большим для сложных AST (mitigation: структура лёгкая — только типы и строки)
- Вычисление trace требует рекурсивного обхода AST (mitigation: глубина AST ≤ 32)
- status `disputed` требует дополнительной логики в Business Facts Engine (Stream 4)

## Связанные решения

- ADR-013: Requirement Expression AST — структура AST, которую отражает trace
- ADR-016: RulesResolver Architecture — как Resolver подготавливает данные для trace
- ADR-003: Rules Catalog effective dates — effective_from в trace связывает с периодом
