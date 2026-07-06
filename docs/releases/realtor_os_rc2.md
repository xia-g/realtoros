# Realtor OS — RC-2 Production Readiness Report

**Date:** 2026-06-10
**Database:** realtoros (PostgreSQL 17)
**Migrations:** 21/21 applied
**Tables:** 52

---

## Scorecard

| Area | Score | Status |
|------|-------|--------|
| **Database Architecture** | 65/100 | ❌ Critical issues |
| **Events** | 82/100 | ⚠️ Test gaps |
| **Knowledge Freshness** | 70/100 | ⚠️ Stub handlers |
| **Compliance** | 90/100 | ✅ |
| **Operations** | 80/100 | ⚠️ |
| **Security** | 75/100 | ⚠️ No agent permissions |
| **AI Governance** | 78/100 | ⚠️ Tool call limit missing |
| **Scalability** | 70/100 | ⚠️ Partitions not executed |

**Overall: 76/100**

---

## Critical Issues (Blockers)

| # | Issue | Severity | Component | Fix |
|---|-------|----------|-----------|-----|
| C1 | `deals` + `deal_participants` no `deleted_at` | 🔴 CRITICAL | Database | Add migration 022 |
| C2 | 0/3 audit tables partitioned | 🔴 CRITICAL | Database | Execute `create_partitions.sql` |
| C3 | No CHECK constraints anywhere | 🔴 CRITICAL | Database | Add score range, status validations |
| C4 | Client→Deal FK = NO ACTION (blocks delete) | 🔴 CRITICAL | Database | Change to SET NULL |
| C5 | Agent has no tool-call limit | 🔴 CRITICAL | AgentRuntime | Add max_tool_calls=20 per request |
| C6 | Embedding handler is stub | 🔴 CRITICAL | Knowledge | Wire actual vector DB call |

---

## High Issues

| # | Issue | Impact | Effort |
|---|-------|--------|--------|
| H1 | No permission model for Agent tools | Agent can call any tool | 3 days |
| H2 | Escalation state lost on restart | In-memory visited[] | 1 day |
| H3 | Approval has no timeout | Tasks stall indefinitely | 1 day |
| H4 | graph_edges FK missing `ondelete=` | Deletion can fail | 1 day |
| H5 | `MAX_ESCALATIONS` not persisted | Survives restarts only | 1 day |

---

## What Passes

- All 21 migrations apply cleanly (after 7 bugs fixed)
- 52 tables with 35 FK constraints
- 158 indexes
- Event chain: emit → handler → graph sync (wired)
- Rate limiter: distributed via PG advisory lock
- Escalation: circuit breaker with MAX_ESCALATIONS=4
- Executive: human approval gate enforced
- Tests: 26 new integration/E2E tests

---

## Comparison: RC-1 → RC-2

| Metric | RC-1 (Jun 9) | RC-2 (Jun 10) |
|--------|--------------|---------------|
| Migrations fixed | 0 | 7 |
| Model bugs fixed | 0 | 13 |
| Production Readiness | 97/100 | **97/100** (plateaued) |
| Architecture Score | 84/100 | **76/100** (honest audit) |

The RC-1 score of 97/100 was inflated by not auditing the database rigorously. RC-2 is a true assessment.
