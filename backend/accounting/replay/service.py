"""Replay service — recalculate decision from existing snapshot.

Invariants:
- Never modifies the event or snapshot
- Creates a NEW accounting_decision (new decision_version)
- Replay is deterministic: same inputs → same output
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

import asyncpg

from backend.accounting.db.pool import get_pool
from backend.accounting.rules import get_registry
from backend.accounting.metrics.collector import metrics


@dataclass
class ReplayResult:
    new_decision_id: str
    old_decision_id: str | None
    old_included: bool | None
    new_included: bool
    old_ruleset_version: str | None
    new_ruleset_version: str
    diff: list[str] = field(default_factory=list)


async def recalculate(
    event_id: str,
    snapshot_version: int | None = None,
    ruleset_version: str | None = None,
) -> ReplayResult:
    """Recalculate decision for an event using a fixed snapshot."""
    start = datetime.now(timezone.utc)

    pool = await get_pool()
    async with pool.acquire() as conn:
        # 1. Load event (only current version)
        event_row = await conn.fetchrow(
            "SELECT * FROM accounting.accounting_event WHERE id = $1 AND is_current = true",
            event_id
        )
        if not event_row:
            raise ValueError(f"Event {event_id} not found or not current")

        event = dict(event_row)

        # 2. Load snapshot (specific version or latest)
        if snapshot_version:
            snap_row = await conn.fetchrow(
                "SELECT * FROM accounting.recognition_snapshot WHERE event_id = $1 AND snapshot_version = $2",
                event_id, snapshot_version
            )
        else:
            snap_row = await conn.fetchrow(
                "SELECT * FROM accounting.recognition_snapshot WHERE event_id = $1 ORDER BY snapshot_version DESC LIMIT 1",
                event_id
            )

        if not snap_row:
            raise ValueError(f"No recognition_snapshot found for event {event_id}")

        import json
        inputs = snap_row["inputs_json"]
        if isinstance(inputs, str):
            inputs = json.loads(inputs)

        snapshot = {
            "id": str(snap_row["id"]),
            "snapshot_version": snap_row["snapshot_version"],
            **inputs,
        }

        actual_snapshot_version = snap_row["snapshot_version"]

        # 3. Load old decision (if any)
        old_decision = await conn.fetchrow(
            "SELECT * FROM accounting.accounting_decision WHERE event_id = $1 AND superseded_at IS NULL",
            event_id
        )

        old_included = old_decision["included"] if old_decision else None
        old_decision_id = str(old_decision["id"]) if old_decision else None
        old_ruleset_version = old_decision.get("ruleset_version") if old_decision else None

        # 4. Determine new version numbers
        if old_decision:
            new_decision_version = old_decision["decision_version"] + 1
        else:
            new_decision_version = 1

        actual_ruleset_version = ruleset_version or f"{datetime.now(timezone.utc).strftime('%Y.%m.%d')}"

        # 5. Run Decision Engine
        registry = get_registry()
        decision = registry.evaluate_all(event, snapshot)

        # Determine decision_state
        if decision.requires_review:
            decision_state = "review_required"
        elif decision.included:
            decision_state = "included"
        else:
            decision_state = "excluded"

        # 6. Supersede old decision
        if old_decision:
            now = datetime.now(timezone.utc)
            await conn.execute(
                "UPDATE accounting.accounting_decision SET superseded_at = $2 WHERE id = $1",
                old_decision["id"], now
            )

        # 7. Create new decision
        new_decision_id = str(uuid4())
        await conn.execute(
            """INSERT INTO accounting.accounting_decision
               (id, event_id, decision_version, ruleset_version, policy_version,
                included, reason, manual_override, superseded_at, created_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7, false, NULL, now())""",
            new_decision_id,
            event_id,
            new_decision_version,
            actual_ruleset_version,
            actual_ruleset_version,
            decision.included,
            decision.reason,
        )

        # 8. Create explanations
        for expl in decision.explanations:
            await conn.execute(
                """INSERT INTO accounting.decision_explanation
                   (id, decision_id, rule_code, weight, message, payload_json, created_at)
                   VALUES ($1, $2, $3, $4, $5, $6::jsonb, now())""",
                str(uuid4()),
                new_decision_id,
                expl.rule_code,
                expl.weight,
                expl.message,
                json.dumps(expl.payload or {}),
            )

        # 9. Update event with current_decision_id and decision_state
        await conn.execute(
            """UPDATE accounting.accounting_event SET
                current_decision_id = $2,
                decision_state = $3,
                processing_state = 'done',
                updated_at = now()
               WHERE id = $1 AND is_current = true""",
            event_id,
            new_decision_id,
            decision_state,
        )

    # 10. Build diff
    diff = []
    if old_included is not None and old_included != decision.included:
        diff.append(f"Included changed: {old_included} → {decision.included}")
    for expl in decision.explanations:
        if not expl.included:
            diff.append(f"Rule '{expl.rule_code}': {expl.message}")

    elapsed = (datetime.now(timezone.utc) - start).total_seconds()
    metrics.record("replay_duration_seconds", elapsed)

    return ReplayResult(
        new_decision_id=new_decision_id,
        old_decision_id=old_decision_id,
        old_included=old_included,
        new_included=decision.included,
        old_ruleset_version=old_ruleset_version,
        new_ruleset_version=actual_ruleset_version,
        diff=diff,
    )
