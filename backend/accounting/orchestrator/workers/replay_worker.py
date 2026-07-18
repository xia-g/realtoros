"""Replay worker — recalculates decisions for existing events."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from backend.accounting.replay.service import recalculate
from backend.accounting.metrics.collector import metrics

logger = logging.getLogger("accounting.worker.replay")


async def process(event_id: str, snapshot_version: int | None = None, ruleset_version: str | None = None) -> str | None:
    """Recalculate a single event decision.

    Returns the new decision_id if successful, None otherwise.
    """
    start = datetime.now(timezone.utc)
    try:
        result = await recalculate(
            event_id=event_id,
            snapshot_version=snapshot_version,
            ruleset_version=ruleset_version,
        )
        logger.info(
            "replay_completed",
            extra={
                "event_id": event_id,
                "new_decision_id": result.new_decision_id,
                "old_included": result.old_included,
                "new_included": result.new_included,
                "diff": result.diff,
            },
        )
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        metrics.record("replay_duration_seconds", elapsed)
        return result.new_decision_id
    except Exception as e:
        logger.error("replay_failed", extra={"event_id": event_id, "error": str(e)})
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        metrics.record("replay_duration_seconds", elapsed, tags={"status": "failed"})
        return None
