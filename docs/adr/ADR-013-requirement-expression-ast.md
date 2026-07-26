# ADR-013: Requirement Expression AST — ALL/ANY/NOT/FACT Tree

**Статус:** Draft  
**Дата:** 2026-07-23  
**Контекст:** Epic 3 — Accounting Compliance & Reporting, Stream 2  
**Автор:** Architect (RealtorOS)

---

## Контекст

Правила Compliance выражают требования в виде логических композиций бизнес-фактов. Пример:

> «Для сдачи декларации по УСН необходимо: revenue_posted И period_closed И (expenses_confirmed ИЛИ payment_received)»

Без структурированного представления:
- Условия зашиты в коде (if-else в RuleEvaluator)
- Невозможно анализировать требования статически (какие факты нужны?)
- Невозможно строить дерево трассировки (почему правило не выполнено?)

## Решение

### 1. AST с четырьмя типами узлов

```python
expression_type: Literal["ALL", "ANY", "NOT", "FACT"]
```

| Тип | Семантика | Children | fact_code |
|:----|:----------|:---------|:----------|
| **ALL** | Все дети должны быть истинны (AND) | 1+ | ❌ |
| **ANY** | Хотя бы один ребёнок истинен (OR) | 1+ | ❌ |
| **NOT** | Отрицание ровно одного ребёнка | 1 | ❌ |
| **FACT** | Бизнес-факт (лист, терминальный узел) | 0 | ✅ |

### 2. Immutable, frozen dataclass

```python
@dataclass(frozen=True)
class RequirementExpression:
    MAX_EXPRESSION_DEPTH: int = 32

    expression_type: Literal["ALL", "ANY", "NOT", "FACT"]
    fact_code: str | None = None
    children: tuple["RequirementExpression", ...] = ()
    criticality: str = "required"  # critical | required | optional | informational
    notes: str = ""
```

### 3. Валидация в конструкторе

- FACT: обязательный `fact_code`, без `children`
- ALL/ANY: минимум 1 `child`, без `fact_code`
- NOT: ровно 1 `child`, без `fact_code`
- Максимальная глубина AST: 32 (конфигурируемая константа)

### 4. ExpressionValidator (отдельный класс)

Выделен в `application/expression_validator.py` для независимого использования:
- Stream 4 (Business Facts Engine): проверка fact_code на существование
- Stream 5 (Eligibility Engine): структурная валидация AST
- Stream 6 (Dependency Engine): проверка duplicate fact_code в ALL/ANY

```python
class ExpressionValidator:
    def __init__(self, max_depth: int = 32):
        self._max_depth = max_depth

    def validate(
        self, expression: RequirementExpression,
        known_fact_codes: set[str] | None = None,
    ) -> list[ValidationError]:
        ...
```

## Обоснование

| Вариант | Минусы |
|:--------|:-------|
| **Plain JSON / dict** | Нет типизации, нет валидации, легко создать некорректное выражение |
| **eval() / exec()** | Опасно, неанализируемо статически |
| **AST с frozen dataclass + валидация** | Безопасно, анализируемо, сериализуемо в JSON |

## Последствия

**Positive:**
- Безопасная композиция: никаких eval/exec
- Статический анализ: можно собрать все нужные fact_code до рантайма
- Детерминированная оценка: ALL/ANY/NOT имеют чёткую семантику
- ExpressionValidator переиспользуется между Stream 4, 5, 6

**Negative:**
- Ограничение глубины 32 — может быть недостаточно для очень сложных правил (mitigation: конфигурируемая константа)
- FACT-узлы ссылаются на `fact_code` — нужен registry бизнес-фактов для валидации
- JSON-сериализация не сохраняет типы Python (criticality как строка, а не enum)

## Связанные решения

- ADR-014: Rule Evaluation Trace — дерево трассировки соответствует AST
- ADR-016: RulesResolver Architecture — как AST передаётся в ResolvedRule
