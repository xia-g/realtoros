# ADR-004: Explainability Pipeline — Dependency Report → Reasoning Graph → LLM Renderer

**Статус:** Draft  
**Дата:** 2026-07-23  
**Контекст:** Epic 3 — Accounting Compliance & Reporting  
**Автор:** Architect (RealtorOS)

---

## Контекст

Пользователь задаёт естественно-языковой вопрос: "Почему декларация УСН не готова?" Система должна ответить человекочитаемым текстом, а не JSON'ом. Предыдущий подход смешивал reasoning (почему не готов) и formatting (как объяснить) в одном LLM-вызове. Это приводило к неточным ответам, т.к. LLM должен был и строить цепочку, и форматировать её.

## Решение

### 1. Разделение: Reasoning Graph + LLM Renderer

```
DependencyReport
    │
    ▼
ReasoningGraphBuilder       ← чистая логика, без LLM
    │
    ▼
ReasoningGraph              ← structured data (serializable JSON)
    │
    ├──→ LLM Renderer       ← только formatting, не reasoning
    │       │
    │       ▼
    │   Answer (human-readable text)
    │
    └──→ Fallback Renderer  ← JSON → UI tree (без LLM)
            │
            ▼
        Raw Graph (UI draws tree)
```

### 2. Reasoning Graph — модель

```python
@dataclass
class ReasoningGraph:
    report_code: str
    status: str                       # ready | partial | not_ready | blocked
    nodes: list[ReasoningNode]
    edges: list[tuple[str, str, str]]  # (from_node, to_node, relation)

@dataclass
class ReasoningNode:
    node_id: str
    type: "report" | "requirement" | "fact" | "source" | "eligibility"
    code: str
    name: str
    status: "ok" | "missing" | "blocked" | "skipped"
    detail: str                       # человекочитаемое пояснение
```

ReasoningGraphBuilder — чистая функция, строит граф из DependencyReport без LLM.

### 3. LLM — только renderer

LLM получает:
- ReasoningGraph (structured JSON)
- Контекст: сегодняшняя дата, сроки
- Язык: "ru" | "en"

LLM НЕ получает:
- Сырые accounting_entries
- Сырые business_events
- Правила каталога

LLM делает:
- Преобразует дерево в связный текст
- Грамматически оформляет
- Расставляет приоритеты (critical first)

LLM НЕ делает:
- Анализ фактов
- Построение цепочки
- Принятие решений

### 4. Fallback без LLM

Если LLM недоступен:
1. ReasoningGraph сериализуется в JSON
2. UI отрисовывает дерево из JSON
3. Каждый узел — expandable/collapsible
4. Статусы — цветовые индикаторы

### 5. Пример

**Input:** "Почему декларация УСН не готова?"

**ReasoningGraph:**
```json
{
  "report_code": "usn_declaration",
  "status": "partial",
  "nodes": [
    {"id": "r1", "type": "report", "code": "usn_declaration", "name": "Декларация по УСН", "status": "partial", "detail": "Частично готова"},
    {"id": "n1", "type": "requirement", "code": "req_revenue_posted", "name": "Выручка проведена", "status": "missing", "detail": "Отсутствует проводка revenue_06_2026"},
    {"id": "n2", "type": "requirement", "code": "req_period_closed", "name": "Период закрыт", "status": "missing", "detail": "Отсутствует событие period_closed за июнь"}
  ],
  "edges": [
    ["r1", "n1", "requires"],
    ["r1", "n2", "requires"]
  ]
}
```

**LLM Output:**
```
Декларация УСН частично готова. Не хватает двух вещей:

1. ❌ Выручка не проведена (critical)
   В учёте отсутствует проводка revenue_06_2026.
   → Создайте проводку или загрузите банковскую выписку за июнь.

2. ❌ Период июнь не закрыт (critical)
   Отсутствует событие period_closed за июнь 2026.
   → Закройте период в бухгалтерском учёте.

После выполнения обоих действий декларация будет готова.
Срок сдачи: 25 октября 2026 (осталось 94 дня).
```

## Обоснование

| Вариант | Минусы |
|:--------|:-------|
| **LLM делает всё (reasoning + formatting)** | Неточные цепочки, hallucination, недетерминированность, дорого |
| **Только rule-based шаблоны** | Хрупкие, не покрывают всех случаев, сложно локализовать |
| **Reasoning Graph + LLM Renderer** | Детерминированная цепочка, LLM только оформляет, fallback без LLM |

## Последствия

**Positive:**
- Reasoning Graph детерминирован и тестируем
- LLM не может ошибиться в цепочке — он только форматирует
- Fallback без LLM: UI рисует дерево из JSON
- Reasoning Graph переиспользуется: dashboard, notifications, webhook

**Negative:**
- Два шага вместо одного — больше latency (mitigation: ReasoningGraphBuilder быстрый, LLM вызов кэшируется)
- LLM может грамматически ошибиться в русском тексте (mitigation: промпт + temperature=0)
- Нужен ReasoningGraphBuilder для каждого типа вопроса

## Связанные решения

- ADR-002: Runtime Business Facts (источник данных для ReasoningGraphBuilder)
