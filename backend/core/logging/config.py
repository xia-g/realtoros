"""Structured logging configuration using structlog.

Loggers: app, audit, lead, knowledge, integration, ai, security.
Environment modes: development (pretty), production (JSON).
"""

from __future__ import annotations

import logging
import sys
from typing import Literal

import structlog

from backend.config import settings


def configure_logging(
    mode: Literal["development", "production"] | None = None,
) -> None:
    """Configure structlog and standard library logging.

    Args:
        mode: Logging mode. Defaults to 'development' when APP_DEBUG is True,
              'production' otherwise.
    """
    if mode is None:
        mode = "development" if settings.APP_DEBUG else "production"

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if mode == "development":
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(
                colors=True,
                sort_keys=False,
            ),
        ]
    else:
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Sync standard library logging to structlog
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if mode == "development" else logging.INFO)

    # Suppress noisy third-party loggers
    for logger_name in ("uvicorn.access", "uvicorn.error", "sqlalchemy.engine"):
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    # Capture standard library logs through structlog
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG if mode == "development" else logging.INFO)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processor=structlog.dev.ConsoleRenderer()
            if mode == "development"
            else structlog.processors.JSONRenderer(),
        )
    )
    root_logger.addHandler(handler)


_LOG_NAMES = frozenset({
    "app", "audit", "lead", "knowledge",
    "integration", "ai", "security",
})


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a named structlog logger.

    Args:
        name: One of: app, audit, lead, knowledge, integration, ai, security.

    Returns:
        A structlog BoundLogger scoped to 'real_estate_os.{name}'.
    """
    if name not in _LOG_NAMES:
        name = "app"
    return structlog.get_logger(f"real_estate_os.{name}")


# Pre-created loggers for convenience
app_logger = get_logger("app")
audit_logger = get_logger("audit")
lead_logger = get_logger("lead")
knowledge_logger = get_logger("knowledge")
integration_logger = get_logger("integration")
ai_logger = get_logger("ai")
security_logger = get_logger("security")
