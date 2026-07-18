# Runbook: Manual Reprocess (DLQ)

**Когда:** Событие в DLQ (`processing_state=failed`, нет retry).

**Шаги:**

1. **Проверить DLQ:**
   ```
   GET /api/v1/accounting/dlq
   ```

2. **Проверить причину:**
   ```
   GET /api/v1/accounting/events/{id}
   # смотреть: last_error, attempt_count
   ```

3. **Исправить причину** (если нужно):
   - Не хватает документа → загрузить
   - Неверный snapshot → создать новую версию

4. **Reprocess:**
   ```
   POST /api/v1/accounting/dlq/{event_id}/reprocess
   ```

5. **Проверить:**
   ```
   GET /api/v1/accounting/events/{id}/decision
   ```
