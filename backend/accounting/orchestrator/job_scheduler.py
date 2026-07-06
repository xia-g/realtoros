"""Job scheduler — polls for events that need processing and dispatches them."""

from __future__ import annotations

import asyncio
import logging

from backend.accounting.models.enums import ProcessingState
from backend.accounting.orchestrator.event_dispatcher import get_next_batch, transition_state
from backend.accounting.orchestrator.retry_policy import DEFAULT_RETRY

logger = logging.getLogger("accounting.orchestrator")


async def poll_recognition(limit: int = 50) -> int:
    """Poll for NEW events and move them to RECOGNIZING."""
    events = await get_next_batch(ProcessingState.NEW, limit)
    for event in events:
        await transition_state(event["id"], ProcessingState.RECOGNIZING)
    return len(events)


async def poll_decision(limit: int = 50) -> int:
    """Poll for READY_FOR_DECISION events and move them to DECIDING."""
    events = await get_next_batch(ProcessingState.READY_FOR_DECISION, limit)
    for event in events:
        await transition_state(event["id"], ProcessingState.DECIDING)
    return len(events)


async def poll_retry(limit: int = 50) -> int:
    """Poll for FAILED events past retry time and reset them."""
    events = await get_next_batch(ProcessingState.FAILED, limit)
    count = 0
    for event in events:
        await transition_state(event["id"], ProcessingState.NEW, clear_decision=True)
        count += 1
    return count
