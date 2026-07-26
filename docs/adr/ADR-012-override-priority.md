# ADR-012: Override Priority — LAW > MANUAL > IMPORT > DEFAULT

**Статус:** Draft  
**Дата:** 2026-07-23  
**Контекст:** Epic 3 — Accounting Compliance & Reporting, Stream 2  
**Автор:** Architect (RealtorOS)

---

## Контекст

Organization Override может быть создан из разных источников:

- **LAW** — автоматическое обновление по закону (новая ставка, новый срок)
- **MANUAL** — ручное изменение бухгалтером через UI
- **IMPORT** — импортировано из внешней системы (1С, Эльба)
- **DEFAULT** — системное значение (из Git)

Для одного `organization_id + rule_code` могут существовать несколько override от разных источников. Например:
- LAW override: новая ставка УСН по закону с 2026 года
- MANUAL override: бухгалтер вручную изменил ставку для своей организации

**Вопрос:** какой override применяется при разрешении правила?

## Решение

### 1. Явная priority chain

```
LAW (0)          ← высший приоритет
  ↓
MANUAL (1)
  ↓
IMPORT (2)
  ↓
DEFAULT (3)      ← низший приоритет
```

Числовой приоритет: **0 = высший, 3 = низший**.

### 2. Правила разрешения конфликтов

```python
_OVERRIDE_PRIORITY: dict[OverrideSource, int] = {
    OverrideSource.LAW:     0,   # высший
    OverrideSource.MANUAL:  1,
    OverrideSource.IMPORT:  2,
    OverrideSource.DEFAULT: 3,   # низший
}
```

1. **Приоритет источника** — применяется override с наивысшим приоритетом (наименьший priority_number)
2. **Равный приоритет** — применяется последняя версия (максимальный effective_from)
3. **Конфликт** — если два override с одинаковым приоритетом *и* одинаковым effective_from → `OverrideConflictError`

### 3. Реализация в Resolver

`RulesResolver._select_best_override()`:

```python
@staticmethod
def _select_best_override(overrides: list[OrganizationOverride]) -> OrganizationOverride | None:
    if not overrides:
        return None
    # Sort by priority (ascending), then by effective_from descending
    sorted_ovs = sorted(
        overrides,
        key=lambda ov: (ov.source.priority, -ov.effective_from.toordinal()),
    )
    best = sorted_ovs[0]
    # Check conflict: same priority AND same effective_from
    for ov in sorted_ovs[1:]:
        if ov.source.priority == best.source.priority and ov.effective_from == best.effective_from:
            raise OverrideConflictError(...)
    return best
```

### 4. Обоснование priority chain

| source | Почему такой приоритет |
|:-------|:----------------------|
| **LAW** (0) | Законодательные изменения должны применяться в первую очередь — их нельзя переопределить вручную (иначе организация нарушает закон) |
| **MANUAL** (1) | Ручные изменения бухгалтера — вторая по значимости; бухгалтер сознательно меняет правило |
| **IMPORT** (2) | Импорт из внешней системы — автоматический, может быть устаревшим или неточным |
| **DEFAULT** (3) | Базовое значение из Git — применяется, если нет ни LAW, ни MANUAL, ни IMPORT override |

## Обоснование

| Вариант | Минусы |
|:--------|:-------|
| **Первый найденный** (было в proposal) | Недетерминировано; порядок зависит от implementation details базы данных; LAW override может быть проигнорирован |
| **Последний по времени** | LAW override может быть перезаписан более поздним manual; нарушение закона |
| **Priority chain + last-write-wins при равном приоритете** | Детерминировано; закон всегда побеждает; бухгалтер может переопределить только в рамках своей компетенции |

## Последствия

**Positive:**
- Детерминированное разрешение конфликтов override
- LAW override всегда применяется — организация не может случайно нарушить закон
- Явный числовой приоритет — легко расширять (добавить новый source с приоритетом 0.5)

**Negative:**
- MANUAL override не может переопределить LAW override — осознанное ограничение (бухгалтер не может отменить закон)
- Дополнительная сложность в Resolver — нужно группировать override по rule_code и применять priority
- ConflictError при равном приоритете и effective_from — может быть неожиданным для администратора (mitigation: понятное сообщение об ошибке)

## Связанные решения

- ADR-011: Rule Storage — как хранятся override с разными source
- ADR-016: RulesResolver Architecture — как Resolver применяет priority chain
- ADR-003: Rules Catalog effective dates — effective_from/effective_to в override
