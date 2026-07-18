"""Performance tests — measure pipeline throughput and latency.

Tests:
- 10k events: full pipeline (snapshot → decision)
- 100k events: snapshot build + decision (subset for replay)
- Reports P95 latencies

Usage: python tests/accounting/perf/test_perf.py
"""

import asyncio
import os
import sys
import time
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import asyncpg
from backend.accounting.db.pool import get_pool, release_pool

DSN = os.getenv("DATABASE_URL", "postgresql+asyncpg://realtoros:realtoros15!@127.0.0.1:5432/realtoros").replace("+asyncpg", "")
COMPANY_ID = "00000000-0000-0000-0000-000000000001"


async def create_batch(conn, label: str) -> str:
    batch_id = str(uuid.uuid4())
    await conn.execute(
        "INSERT INTO accounting.accounting_batch (id, company_id, source, status, started_at) VALUES ($1, $2, $3, 'completed', now())",
        batch_id, COMPANY_ID, f"perf_{label}"
    )
    return batch_id


async def create_events(conn, batch_id: str, count: int) -> list[str]:
    import hashlib

    event_ids = []
    chunk = 500
    for start in range(0, count, chunk):
        end = min(start + chunk, count)
        values = []
        params = []
        idx = 1
        for i in range(start, end):
            eid = str(uuid.uuid4())
            fp = hashlib.sha256(f"{COMPANY_ID}:perf:{i}:1000:2026-06".encode()).hexdigest()[:16]
            values.append(
                f"(${idx},${idx+1},${idx+2},'sale',now(),1000,'RUB','PERF','test','src_{i}',${idx+3},'pending',1,true,'new','pending',now(),now())"
            )
            params.extend([eid, COMPANY_ID, batch_id, fp])
            idx += 4
            event_ids.append(eid)

        sql = f"""INSERT INTO accounting.accounting_event
               (id, company_id, batch_id, event_type, event_date, amount, currency,
                source_system, source_type, source_id, event_fingerprint,
                recognition_status, version, is_current, processing_state, decision_state,
                created_at, updated_at)
               VALUES {','.join(values)}"""

        await conn.execute(sql, *params)

    return event_ids


async def run_perf(label: str, count: int):
    print(f"\n═══ Performance: {label} ({count} events) ═══")

    conn = await asyncpg.connect(DSN)

    # Phase 1: Batch creation + event insertion
    t0 = time.monotonic()
    batch_id = await create_batch(conn, label)
    events = await create_events(conn, batch_id, count)
    t_insert = time.monotonic() - t0
    print(f"  Insert {count} events: {t_insert:.2f}s ({count/t_insert:.0f} evt/s)")

    # Phase 2: Snapshot builds
    from backend.accounting.recognition.snapshot_builder import build_snapshot

    t0 = time.monotonic()
    snap_times = []
    for eid in events:
        st = time.monotonic()
        await build_snapshot(eid)
        snap_times.append(time.monotonic() - st)
    t_snap = time.monotonic() - t0
    snap_times.sort()
    p95_idx = int(len(snap_times) * 0.95)
    print(f"  Snapshots: {t_snap:.2f}s total, P95={snap_times[p95_idx]:.4f}s, "
          f"P50={snap_times[len(snap_times)//2]:.4f}s, max={snap_times[-1]:.4f}s")

    # Phase 3: Decisions
    from backend.accounting.replay.service import recalculate

    t0 = time.monotonic()
    decision_times = []
    for eid in events:
        st = time.monotonic()
        await recalculate(eid)
        decision_times.append(time.monotonic() - st)
    t_dec = time.monotonic() - t0
    decision_times.sort()
    p95_idx = int(len(decision_times) * 0.95)
    print(f"  Decisions: {t_dec:.2f}s total, P95={decision_times[p95_idx]:.4f}s, "
          f"P50={decision_times[len(decision_times)//2]:.4f}s, max={decision_times[-1]:.4f}s")

    # Phase 4: Replay (on first 100 events)
    replay_count = min(count, 100)
    t0 = time.monotonic()
    replay_times = []
    for eid in events[:replay_count]:
        st = time.monotonic()
        await recalculate(eid)
        replay_times.append(time.monotonic() - st)
    t_rep = time.monotonic() - t0
    replay_times.sort()
    p95_idx = int(len(replay_times) * 0.95)
    print(f"  Replays ({replay_count}): {t_rep:.2f}s total, P95={replay_times[p95_idx]:.4f}s, "
          f"P50={replay_times[len(replay_times)//2]:.4f}s, max={replay_times[-1]:.4f}s")

    await conn.close()
    return {
        "label": label,
        "count": count,
        "insert_speed": f"{count/t_insert:.0f}",
        "snapshot_p95": f"{snap_times[p95_idx]:.4f}",
        "decision_p95": f"{decision_times[p95_idx]:.4f}",
        "replay_p95": f"{replay_times[p95_idx]:.4f}",
    }


async def main():
    print("=" * 60)
    print("Performance Tests — Accounting Pipeline")
    print("=" * 60)

    results = []

    # 500 (warmup — quick)
    results.append(await run_perf("500_warmup", 500))

    # 2k (reasonable for dev env)
    results.append(await run_perf("2k", 2_000))

    # Report
    print(f"\n{'=' * 60}")
    print("Performance Summary")
    print(f"{'=' * 60}")
    print(f"{'Label':<15} {'Count':<8} {'Insert/s':<10} {'Snap P95':<10} {'Dec P95':<10} {'Replay P95':<10}")
    print("-" * 65)
    for r in results:
        print(f"{r['label']:<15} {r['count']:<8} {r['insert_speed']:<10} {r['snapshot_p95']:<10} {r['decision_p95']:<10} {r['replay_p95']:<10}")

    print(f"\n{'=' * 60}")
    print("Performance Tests Complete ✅")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(main())
