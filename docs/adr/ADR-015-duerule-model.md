# ADR-015: DueRule Model — гибкий DSL для сроков

**Статус:** Draft  
**Дата:** 2026-07-23  
**Контекст:** Epic 3 — Accounting Compliance & Reporting, Stream 2  
**Автор:** Architect (RealtorOS)

---

## Контекст

Сроки сдачи отчётности и уплаты налогов разнообразны:

- «25-го числа через 3 месяца после отчётного периода» (offset)
- «28-го числа месяца, следующего за отчётным кварталом» (expression)
- «0 0 25 3 *» (cron — для сложных случаев, например, НДС поквартально)
- Единый срок для всех: «не позднее 25 марта»

Без гибкого DSL сроки приходится хардкодить в RuleEvaluator. Каждый новый тип срока требует изменения кода.

## Решение

### 1. DueRule — три формата

```python
@dataclass(frozen=True)
class DueRule:
    rule_type: Literal["offset", "expression", "cron"]
    raw: str
    description: str
```

| Формат | Пример | Когда применять |
|:-------|:-------|:----------------|
| **offset** | `+3M 25d` | Типовые сроки: «через N месяцев M-го числа» |
| **expression** | `25th of month after quarter` | Естественно-языковые описания (для UI) |
| **cron** | `0 0 25 3 *` | Сложные/нерегулярные сроки: «последний день квартала» |

### 2. DueRuleParser — отдельный интерфейс

```python
class DueRuleParser(ABC):
    @abstractmethod
    def parse(self, rule: DueRule) -> DueRuleAST:
        ...

    @abstractmethod
    def compute(
        self, ast: DueRuleAST,
        period_year: int,
        period_month: int | None = None,
        period_quarter: int | None = None,
    ) -> date:
        ...
```

- **Парсер** — превращает текстовый DueRule в AST
- **Вычислитель** — по AST + период вычисляет конкретную дату
- Реализация в `infrastructure/due_rule/parser.py`

### 3. Валидация

- `rule_type` — только из допустимых (offset, expression, cron)
- `raw` — непустой
- При стартовой валидации: все DueRule парсятся для проверки корректности
- Если DueRule не парсится → `DueRuleParseError`

### 4. Вычисление дедлайна

```python
def compute_deadline(self, period: str, calendar: ...) -> date:
    """period: '2026-Q1', '2026-06', '2025'"""
    ...
```

- `period` — отчётный период в формате ISO
- `calendar` — бизнес-календарь (праздники, переносы)
- Результат — конкретная дата: `date(2026, 3, 25)`

## Обоснование

| Вариант | Минусы |
|:--------|:-------|
| **Только offset** | Не покрывает сложные случаи (последний день квартала, следующий рабочий день после праздника) |
| **Только cron** | Нечитаем для бухгалтера; сложно дебажить |
| **Три формата + парсер** | Гибко: простые случаи — offset, сложные — cron, для UI — expression |

## Последствия

**Positive:**
- Новый тип срока — просто новый формат в DueRule, не изменение кода
- Парсер можно тестировать изолированно
- description — человекочитаемое пояснение для UI
- Интеграция с бизнес-календарём для учёта праздников/переносов

**Negative:**
- Три формата = три парсера + три тестовых набора
- Expression (естественный язык) — сложнее всего парсить; может потребовать NLP (mitigation: ограниченный набор шаблонов)
- Cron-формат избыточен для типовых налоговых сроков (mitigation: резервный формат для редких случаев)

## Связанные решения

- ADR-016: RulesResolver Architecture — DueRule передаётся в ResolvedRule
- Stream 8 (Compliance Timeline): использует DueRule для построения таймлайна
