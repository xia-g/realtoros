# Accounting Pipeline — Release Checklist

**Версия:** Phase 2.5

---

## Go-Live Checklist

### Code
- [ ] All migrations applied (028 head)
- [ ] E2E tests pass
- [ ] Reliability tests pass (4 scenarios, 32 checks)
- [ ] No direct UPDATE/DELETE on accounting_event

### Data
- [ ] Batches have unique external_batch_key
- [ ] Events have unique event_fingerprint (app-level check)
- [ ] Snapshots exist for all events before decisions
- [ ] DLQ is empty

### API
- [ ] GET /accounting/events — returns data
- [ ] POST /accounting/replay — deterministic
- [ ] POST /accounting/dlq/{id}/reprocess — works
- [ ] GET /accounting/metrics — returns metrics

### Monitoring
- [ ] Metrics endpoint working
- [ ] Structured logging active
- [ ] trace_id propagated

---

## Rollback

### Если проблема в правилах
```bash
# Просто откатить ruleset
# Старые решения не удаляются, только supersede
```

### Если проблема в миграции
```bash
python -m alembic downgrade -1
```

### Если проблема в API
```bash
# Отключить accounting роутер в router.py
# Перезапустить API
```

---

## Alerts (рекомендуемые)

| Alert | Threshold | Action |
|-------|-----------|--------|
| DLQ size > 10 | 10 events | Check runbook: reprocess |
| Processing queue > 1000 | 1000 NEW events | Scale workers |
| Error rate > 5% | 5% failed | Check worker logs |
| Replay inconsistency | diff detected | Investigate snapshot |

---

## Ownership

| Component | Owner |
|-----------|-------|
| Schema (026–028) | Backend |
| Orchestrator | Backend |
| Rules | Backend |
| API | Backend |
| E2E tests | QA |
| Performance | DevOps |

---

## Go/No-Go

**Решение:** ✅ **Go — можно начинать Phase 3 (Ledger)**

**Обоснование:**
- 32/32 reliability tests passed
- All SLOs met (Decision P95=35ms, Replay P95=43ms)
- E2E pipeline complete
- Dedup working (fingerprint check)
- Snapshot invariant enforced
- Replay deterministic
