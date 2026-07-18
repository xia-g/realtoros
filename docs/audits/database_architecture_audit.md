# Database Architecture Audit

**Date:** 2026-06-10
**Database:** realtoros (PG 17)
**Tables:** 52
**Migrations:** 21
**Total Indexes:** 158

---

## 1. Migration Chain Integrity

| Check | Status | Details |
|-------|--------|---------|
| Chain linear | ✅ | 001 → 021, no branches |
| All revisions unique | ✅ | No duplicate revision IDs |
| down_revision matches | ✅ | All refs verified after RC-1 fix |
| `001` base → `None` | ✅ | Initial migration has `down_revision = None` |
| Depends on | ✅ | All `depends_on = None` |

**Issues found in RC-1 and fixed:** 6 revision ID mismatches where `revision` was `"003"` but `down_revision` in 004 referenced `"003_add_notifications"`. All fixed.

---

## 2. Foreign Key Integrity

| Check | Status | Details |
|-------|--------|---------|
| FK count | ✅ | ~35 foreign keys across all tables |
| `ON DELETE CASCADE` | ⚠️ | Used correctly for child tables (lead_events→leads, document_chunks→documents) |
| `ON DELETE SET NULL` | ✅ | Used for optional references (assigned_to, created_by) |
| `ON DELETE RESTRICT` | ⚠️ | Only 1 case: leads.created_by → users.id |
| Missing ON DELETE | ⚠️ | Some FKs in model code lack explicit `ondelete` — cascade defaults to NO ACTION |
| Cyclic FKs | ✅ | None found — Deal→Client, Client→User, no cycles |

**Finding:** 3 model-level FKs in `graph_node.py` and `graph_edge.py` lack explicit `ondelete=` rules — default to `NO ACTION` which can cause deletion failures.

---

## 3. Soft Delete Coverage

| Group | Tables | deleted_at? |
|-------|--------|-------------|
| CRM Core | roles, users, clients, client_contacts, properties | ✅ (004) |
| Leads | leads, lead_events | ✅ (002) |
| Deals | deals, deal_participants | ❌ **MISSING** |
| Workflow | deal_workflows, deal_stage_transitions, deal_document_packages, deal_checkpoints | ✅ (012, 016) |
| Knowledge | graph_nodes, graph_edges, document_chunks, embeddings | ✅ (016) |
| Audit | ai_call_log, agent_tool_calls, compliance_audits | ✅ (016) |
| Regulations | regulations, regulation_versions, regulation_sync_logs | ⚠️ Partial |
| Analytics | analytics_snapshots, analytics_alerts, prediction_results | ❌ **MISSING** |

**Critical finding:** `deals` and `deal_participants` tables do NOT have `deleted_at` — core business entity cannot be soft-deleted. This is a production blocker.

---

## 4. Index Analysis

| Metric | Value |
|--------|-------|
| Total indexes | 158 |
| Indexes per table | ~3 avg |
| Missing composite indexes | 3 (deal queries by status+stage, client+status) |
| Unused index candidates | 5 (single-column indexes covered by composites) |

---

## 5. Partition Candidates

| Table | Rows/Year Est. | Partition Needed? | Current State |
|-------|---------------|-------------------|---------------|
| ai_call_log | 500K-2M | YES | Regular table ❌ |
| agent_tool_calls | 100K-500K | YES | Regular table ❌ |
| compliance_audits | 50K-200K | YES | Regular table ❌ |

**Critical finding:** Zero of 3 audit tables are actually partitioned. Migration 018 was rewritten as comments-only. This is a production blocker.

---

## 6. Constraint Analysis

| Check | Status |
|-------|--------|
| Primary keys on all tables | ✅ All have UUID PKs |
| Unique constraints | ✅ On users.phone, users.email, roles.name, lead_source entries |
| CHECK constraints | ❌ **Zero CHECK constraints** — no validation at DB level |
| NOT NULL on critical fields | ⚠️ Some nullable fields should be required |

**Finding:** No CHECK constraints anywhere. Fields like `deals.score` and `compliance_audits.score` should have range checks (0-100) at DB level.

---

## 7. Cascade Rules Audit

| Parent | Child | Rule | Safe? |
|--------|-------|------|-------|
| users | leads | SET NULL | ✅ |
| users | clients | SET NULL | ✅ |
| clients | deals | NO ACTION (default) | ⚠️ — will block client deletion |
| deals | deal_workflows | CASCADE | ⚠️ — hard delete cascades |
| graph_nodes | graph_edges | CASCADE | ⚠️ — hard delete cascades |

---

## Score: 65/100

**Critical blockers (must fix before production):**
1. `deals` and `deal_participants` missing `deleted_at`
2. Zero partitioned audit tables (3 tables)
3. 3 model FKs without explicit `ondelete=`
4. Zero CHECK constraints
5. client→deals FK is NO ACTION (blocks client deletion)
