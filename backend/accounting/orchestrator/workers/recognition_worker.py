"""Recognition worker — builds snapshots for NEW events."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from backend.accounting.db.pool import get_pool
from backend.accounting.models.enums import ProcessingState
from backend.accounting.orchestrator.event_dispatcher import (
    get_next_batch,
    transition_state,
    mark_failed,
)
from backend.accounting.orchestrator.retry_policy import DEFAULT_RETRY
from backend.accounting.recognition.snapshot_builder import build_snapshot
from backend.accounting.metrics.collector import metrics

logger = logging.getLogger("accounting.worker.recognition")


async def process(event_id: str) -> bool:
    """Process a single event: build recognition snapshot.

    Stateless, one event per call. Safe to retry.
    """
    start = datetime.now(timezone.utc)
    try:
        snapshot = await build_snapshot(event_id)
        logger.info("snapshot_built", extra={"event_id": event_id, "snapshot_version": snapshot["snapshot_version"]})
        await transition_state(event_id, ProcessingState.READY_FOR_DECISION)
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        metrics.record("event_processing_seconds", elapsed, tags={"stage": "recognition"})
        return True
    except Exception as e:
        logger.error("recognition_failed", extra={"event_id": event_id, "error": str(e)})
        await mark_failed(event_id, str(e))
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        metrics.record("event_processing_seconds", elapsed, tags={"stage": "recognition_failed"})
        return False
