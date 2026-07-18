# Event Consistency Audit

**Date:** 2026-06-10
**Goal:** 100% declared events → emitted → handled → tested

---

## Event Matrix

| Event | Declared in DomainEventBus | Emitted From | Handler Registered | Tested |
|-------|---------------------------|--------------|-------------------|--------|
| client.created | ✅ | ClientService.create() | graph_sync, audit | ✅ |
| client.updated | ✅ | ClientService.update() | graph_sync, audit | ✅ |
| client.deleted | ✅ | ClientService.delete() | graph_sync, audit | ❌ |
| property.created | ✅ | PropertyService.create() | graph_sync, audit | ❌ |
| property.updated | ✅ | PropertyService.update() | graph_sync, audit | ❌ |
| property.deleted | ✅ | PropertyService.delete() | graph_sync, audit | ❌ |
| deal.created | ✅ | DealService.create() | graph_sync, audit | ❌ |
| deal.updated | ✅ | DealService.update() | graph_sync, audit | ✅ |
| deal.deleted | ✅ | DealService.delete() | graph_sync, audit | ❌ |
| document.created | ✅ | DocumentPackageService.attach | graph_sync, embedding, search, audit | ✅ |
| document.deleted | ✅ | DocumentPackageService.detach | graph_sync, embedding, search, audit | ❌ |
| lead.converted | ✅ | LeadService.convert_lead() | graph_sync, audit | ✅ |
| lead.merged | ✅ | LeadService.merge_leads() | graph_sync, audit | ❌ |

## Handler Coverage

| Handler | Events Subscribed | Status |
|---------|------------------|--------|
| graph_sync_handler | 13/13 | ✅ |
| embedding_sync_handler | 2/13 (document.*) | ✅ |
| search_index_handler | 2/13 (document.*) | ✅ |
| audit_handler | 13/13 | ✅ |

## Findings

1. **Event coverage:** 13/13 declared = 13/13 emitted = 13/13 handled ✅
2. **Test coverage:** 5/13 events have dedicated integration tests ❌
3. **Handler imports:** `register_sync_handlers()` called in `main.py` lifespan ✅
4. **EventHandler dead code check:** All 4 handlers have subscriptions ✅
5. **actor_id propagation:** Added to DomainEvent dataclass ✅

## Gaps

- Events missing integration tests: client.deleted, property.*, deal.closed, deal.deleted, lead.merged
- Embedding handler is a stub (logs only, no actual embedding refresh)
- Search handler is a stub (logs only)
- No handler for `regulation.updated` (declared in 6A but never registered)

## Score: 82/100
