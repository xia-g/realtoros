# Runbook: DLQ Cleanup

**Когда:** DLQ накопила события, которые больше не нужны.

**Шаги:**

1. **Просмотреть DLQ:**
   ```
   GET /api/v1/accounting/dlq?limit=500
   ```

2. **Для каждого события решить:**
   - Можно исправить → reprocess
   - Не нужно → supersede (новая версия с is_current=false)
   - Ошибочное → удалить физически (только admin)

3. **Физическое удаление (только если уверены):**
   ```sql
   BEGIN;
   DELETE FROM accounting.decision_explanation
   WHERE decision_id IN (SELECT id FROM accounting.accounting_decision WHERE event_id = '<id>');
   DELETE FROM accounting.accounting_decision WHERE event_id = '<id>';
   DELETE FROM accounting.recognition_snapshot WHERE event_id = '<id>';
   DELETE FROM accounting.event_document WHERE event_id = '<id>';
   DELETE FROM accounting.event_transaction WHERE event_id = '<id>';
   DELETE FROM accounting.accounting_event WHERE id = '<id>';
   COMMIT;
   ```
