# Recovery Playbook — Accounting Binding v1.3

Операции восстановления для бухгалтерского контура.

---

## CASE 1: Outbox Backlog

**Симптом:** `ab_outbox_backlog > 0` длительное время, posting не выполняется.

**Причина:** Worker упал, outbox-сообщения зависли в `pending`.

**Восстановление:**

```bash
# 1. Проверить backlog
curl -s https://api.spcnn.ru/health | jq '.dependencies.outbox'

# 2. Запустить replay worker
curl -X POST https://api.spcnn.ru/api/v1/system/outbox/flush

# 3. Если worker не стартует — прямой рестарт очереди
# (в зависимости от брокера)
```

**Проверка:**
- `ab_outbox_backlog == 0`
- `ab_posting_total{result="posted"}` увеличился

---

## CASE 2: Posting Partial Failure

**Симптом:** `ab_posting_total{result="failed"} > 0`, документ `APPROVED` но `POSTED` нет.

**Причина:** DB недоступна mid-commit, timeout, race condition.

**Восстановление:**

```bash
# 1. Найти документы в APPROVED без journal_entry
curl -s https://api.spcnn.ru/api/v1/posting/pending

# 2. Re-run posting (идемпотентно — UNIQUE hash)
curl -X POST https://api.spcnn.ru/api/v1/replay/{document_id}?mode=full
```

**Идемпотентность гарантирует:** повторный POST того же документа → DUPLICATE, не двойная проводка.

---

## CASE 3: Corrupted Approval Revision

**Симптом:** `StaleApprovalError`, документ `APPROVED` но `approved_mapping_hash ≠ mapping_hash`.

**Причина:** enriched_document изменился после approval (re-mapping изменил счета).

**Восстановление:**

```bash
# 1. Reject текущий approval (сброс revision)
# (через ApprovalWorkflow: REVIEW → REJECTED)
# (через UI или API)

# 2. Вернуть в DRAFT
# (ApprovalWorkflow: REJECTED → DRAFT)

# 3. Re-map с новыми правилами
curl -X POST https://api.spcnn.ru/api/v1/replay/{document_id}?mode=from_enrichment
```

**Проверка:**
- `approval_revision == 0` (сброшен)
- `approved_mapping_hash == ""` (сброшен)
- После replay: `approval_revision == 1`, `approved_mapping_hash == current_mapping_hash`

---

## CASE 4: Replay Mismatch

**Симптом:** Результат replay отличается от оригинального прогона.

**Причина:** Правила enrichment/mapping изменились между прогонами.

**Восстановление:**

```bash
# 1. Проверить, какой этап даёт расхождение
# Replay с разными mode:
curl -X POST https://api.spcnn.ru/api/v1/replay/{id}?mode=from_enrichment
curl -X POST https://api.spcnn.ru/api/v1/replay/{id}?mode=from_mapping

# 2. Если enriched совпадает — проблема в mapping:
# проверить mapping правила (accountBook)
# проверить mapping_hash

# 3. Если enriched не совпадает — проверить enrichment:
# проверить политику ReplayPolicy.ENRICHMENT
# (должна быть REUSE для стабильности)
```

**Коррекция:** rebuild от проблемного этапа. **Никогда** не править journal_entry вручную.

---

## CASE 5: DB Restore / Full Rebuild

**Симптом:** База данных восстановлена из бэкапа, данные в несогласованном состоянии.

**Причина:** Восстановление из бэкапа без учёта append-only семантики.

**Восстановление:**

```bash
# 1. Убедиться, что normalized_documents сохранены (source of truth)
# (внешнее хранилище: S3, файловая система, OCR нода)

# 2. Очистить проекции (disposable)
DELETE FROM accounting_documents;
DELETE FROM journal_entries;
DELETE FROM outbox_events;

# 3. Полный replay всех normalized_documents
for doc_id in $(list_all_docs); do
  curl -X POST "https://api.spcnn.ru/api/v1/replay/${doc_id}?mode=full"
done

# 4. Перестроить отчёты
curl -X POST https://api.spcnn.ru/api/v1/reporting/rebuild
```

**Время восстановления:** O(n) где n — количество normalized_documents.

---

## Правила восстановления

1. **Никогда** не UPDATE journal_entry — только REVERSE + NEW
2. **Никогда** не править accounting_document вручную — только replay
3. **Никогда** не менять normalized_document — он frozen
4. **Идемпотентность** — главный инструмент recovery
5. **Canonical hash** — единственный идентификатор для dedup
6. **Если сомневаешься — rebuild из normalized_document**
