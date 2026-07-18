# Runbook: Ruleset Rollout

**Когда:** Добавление/изменение правила в Rule Engine.

**Шаги:**

1. **Написать правило** в `backend/accounting/rules/rules/`
   ```python
   class MyNewRule(Rule):
       rule_code = "my_new_rule"
       priority = 50
       def supports(self, event, snapshot): ...
       def evaluate(self, event, snapshot): ...
   ```

2. **Зарегистрировать** в `backend/accounting/rules/__init__.py`

3. **Протестировать:**
   ```bash
   python -m pytest tests/accounting/e2e/
   ```

4. **Задеплоить** код правил

5. **Массовый пересчёт:**
   ```python
   for event_id in affected_events:
       await recalculate(event_id, ruleset_version="2026.06.16")
   ```

6. **Проверить дифф:**
   - Старое решение vs новое
   - Убедиться, что изменилось только ожидаемое
