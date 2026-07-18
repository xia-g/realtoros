# Scalability Projection

**Date:** 2026-06-10
**Current Dataset:** 0 transactions (clean install)

---

## Assumptions

| Metric | Value | Source |
|--------|-------|--------|
| Deals/month (small agency) | 50 | Industry avg |
| Deals/month (mid agency) | 500 |
| Deals/month (enterprise) | 5,000 |
| AI calls per deal | ~20 | 10 compliance + 5 analysis + 5 agent |
| Agent tool calls per deal | ~50 | Various MCP tools |
| Compliance audits per deal | ~5 | Per regulation + recheck |
| Avg audit row size | ~500 bytes | JSON + metadata |
| Retention | 12 months | Partitioning strategy |

---

## 1K User / Small Agency

| Table | 1 Month | 12 Months | 24 Months | 36 Months |
|-------|---------|-----------|-----------|-----------|
| ai_call_log | 1,000 rows | 12,000 rows | 24,000 rows | 36,000 rows |
| agent_tool_calls | 2,500 rows | 30,000 rows | 60,000 rows | 90,000 rows |
| compliance_audits | 250 rows | 3,000 rows | 6,000 rows | 9,000 rows |
| Total storage | ~3 MB | ~36 MB | ~72 MB | ~108 MB |

**Verdict:** ✅ No partitioning needed — fits in memory. Composite indexes sufficient.

---

## 10K User / Mid Agency

| Table | 1 Month | 12 Months | 24 Months | 36 Months |
|-------|---------|-----------|-----------|-----------|
| ai_call_log | 10,000 rows | 120,000 rows | 240,000 rows | 360,000 rows |
| agent_tool_calls | 25,000 rows | 300,000 rows | 600,000 rows | 900,000 rows |
| compliance_audits | 2,500 rows | 30,000 rows | 60,000 rows | 90,000 rows |
| Total storage | ~30 MB | ~360 MB | ~720 MB | ~1.1 GB |
| Partition count | 1/mo | 12 | 24 | 36 |

**Verdict:** ⚠️ **Partitioning required at 12 months.** Query performance degrades after 100K rows in audit tables without partition pruning. Monthly partitions keep each partition under 10K rows.

---

## 100K User / Enterprise

| Table | 1 Month | 12 Months | 24 Months | 36 Months |
|-------|---------|-----------|-----------|-----------|
| ai_call_log | 100,000 rows | 1,200,000 rows | 2,400,000 rows | 3,600,000 rows |
| agent_tool_calls | 250,000 rows | 3,000,000 rows | 6,000,000 rows | 9,000,000 rows |
| compliance_audits | 25,000 rows | 300,000 rows | 600,000 rows | 900,000 rows |
| Total storage | ~300 MB | ~3.6 GB | ~7.2 GB | ~10.8 GB |
| Partition count | 1/mo | 12 | 24 | 36 |

**Verdict:** ❌ **Partitioning mandatory.** Without partitions:
- `ai_call_log` at 3.6M rows: sequential scan on every query
- GIN index on JSONB grows to 2GB+
- Backup/restore time becomes prohibitive (>1 hour)

---

## Partition Requirements by Scale

| Scale | Partitions Needed | Auto-create | Retention | Storage |
|-------|------------------|-------------|-----------|---------|
| Small (<1K deals/mo) | Optional | Monthly cron | Manual | <100 MB |
| Mid (1K-10K deals/mo) | ✅ Required | Monthly cron | 12-month drop | <5 GB |
| Enterprise (>10K deals/mo) | ✅ Required | Weekly cron | 6-month drop | <50 GB |

## Key Bottlenecks

1. **`pgvector` embeddings** — `Embeddings` table grows by ~500 rows/deal (100 chunks × 5 docs). At 10K deals, that's 5M embeddings. ANN index required beyond 1M.
2. **`compliance_audits.details` (JSONB)** — GIN index size grows with table size. Partitioning keeps each index <1 GB.
3. **`agent_tool_calls.input/output` (JSONB)** — Largest table by storage. Most impactful for partitioning.

## Score: 70/100
