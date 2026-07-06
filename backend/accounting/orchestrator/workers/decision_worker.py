"""Decision worker — executes Rule Engine on ready events."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from backend.accounting.models.enums import ProcessingState
from backend.accounting.orchestrator.event_dispatcher import transition_state, mark_failed
from backend.accounting.replay.service import recalculate
from backend.accounting.metrics.collector import metrics

logger = logging.getLogger("accounting.worker.decision")


async def process(event_id: str) -> bool:
    """Process a single event: run Rule Engine and create decision.

    Uses ReplayService.recalculate() internally (same code path).
    Stateless, one event per call. Safe to retry.
    """
    start = datetime.now(timezone.utc)
    try:
        result = await recalculate(event_id)
        logger.info(
            "decision_created",
            extra={
                "event_id": event_id,
                "decision_id": result.new_decision_id,
                "included": result.new_included,
                "ruleset": result.new_ruleset_version,
                "diff_count": len(result.diff),
            },
        )
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        metrics.record("decision_duration_seconds", elapsed)
        return True
    except Exception as e:
        logger.error("decision_failed", extra={"event_id": event_id, "error": str(e)})
        await mark_failed(event_id, str(e))
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        metrics.record("decision_duration_seconds", elapsed, tags={"status": "failed"})
        return False
