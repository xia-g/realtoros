# Reconciliation Performance — Technical Backlog

## Current State

```yaml
algorithm: O(n²) nested loop matching
matching_p95: ~19 sec (for ~600 items × 600 items)
bottleneck: full scan of all ledger × bank items
acceptable:     < 5 sec
production:    < 2 sec
```

## Candidate Improvements

### 1. Candidate Pruning (High Priority)

Pre-filter before matching:
- Date window: ±3 day sliding window
- Amount bucket: group by amount rounded to nearest 100/1000
- Direction match: only compare inflow↔inflow, outflow↔outflow

**Expected gain:** O(n²) → O(k·m) where k = items in window

### 2. Hash-Based Bucket Matching (Medium)

```python
def hash_bucket(item):
    return hashlib.sha256(f"{item.amount:.0f}|{item.direction}".encode()).hexdigest()[:4]
```

Only compare items in the same hash bucket.

**Risk:** False negatives for fuzzy matches with small amount differences

### 3. Parallel Workers (Medium)

```python
async with asyncio.TaskGroup() as tg:
    for window in date_windows(period_from, period_to):
        tg.create_task(match_window(window))
```

Partition by week/month, run in parallel.

**Expected gain:** 2–4× speedup (limited by connection pool)

### 4. Preindexed Matching (Low)

Materialize a `reconciliation_index` table:
- `(amount_bucket, direction, date) → item_id`
- Updated incrementally after each import
- Deterministic rebuild via replay

**Risk:** New table (violates freeze) — defer to post-RC1

### 5. Incremental Runs (Low)

Only match new items since last run:
- Store last_run timestamp
- Fetch only delta items
- Merge with previous matches

**Risk:** Gaps may appear if old items change (impossible because immutable)

## Acceptance

| Metric | Current | Target | Priority |
|--------|---------|--------|----------|
| 1k × 1k matching | ~19s | <5s | High |
| 10k × 10k | N/A | <30s | Medium |
| Deterministic hash | ✅ | ✅ | Required |
| Same explainability | ✅ | ✅ | Required |

## Decision

**Deferred to post-RC1.** Do not change matching algorithm before production import.
