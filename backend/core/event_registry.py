"""Event Registry — single point of handler registration.

Ensures handlers are registered exactly once.
Replaces dual registration in main.py + agent.py.
"""

from __future__ import annotations

from structlog import get_logger

logger = get_logger(__name__)

_registry_initialized = False


def ensure_event_registry() -> None:
    """Initialize the event registry exactly once.

    Safe to call multiple times — idempotent guard prevents
    duplicate handler registration.
    """
    global _registry_initialized
    if _registry_initialized:
        logger.info("event_registry_already_initialized")
        return

    from backend.core.domain_events import get_event_bus
    from backend.core.event_handlers import register_sync_handlers

    register_sync_handlers(get_event_bus())
    _registry_initialized = True
    logger.info("event_registry_initialized")


def is_registry_initialized() -> bool:
    """Check if the registry has been initialized."""
    return _registry_initialized
