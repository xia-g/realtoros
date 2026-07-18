# Runbook: Event Backfill

**Когда:** Необходимо создать accounting_event для исторических данных.

**Шаги:**

1. **Создать batch:**
   ```sql
   INSERT INTO accounting.accounting_batch (id, company_id, source, status, started_at)
   VALUES (gen_random_uuid(), '<company_id>', 'backfill_2025', 'completed', now());
   ```

2. **Создать события** (через API или прямой INSERT):
   ```python
   # Использовать backend/accounting/db/helpers.check_fingerprint_unique()
   # перед каждым INSERT
   ```

3. **Построить snapshot:**
   ```python
   from backend.accounting.recognition.snapshot_builder import build_snapshot
   await build_snapshot(event_id)
   ```

4. **Запустить решение:**
   ```python
   from backend.accounting.replay.service import recalculate
   await recalculate(event_id)
   ```

5. **Проверить:**
   ```
   GET /api/v1/accounting/events/{id}/decision
   GET /api/v1/accounting/events/{id}/explanations
   ```
