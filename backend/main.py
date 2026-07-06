"""FastAPI application entry point.

Runtime foundation:
  - Structlog structured logging
  - Request context middleware
  - Global error handlers
  - Health check endpoints
  - Startup validation
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.router import api_router
from backend.api.routes.health import router as health_router
from backend.config import settings
from backend.core.error_handlers import register_error_handlers
from backend.core.logging import configure_logging, get_logger
from backend.core.middleware import RequestContextMiddleware
from backend.core.observability import DatabaseHealthCheck


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown."""

    # ── Startup ────────────────────────────────────────────────
    logger = get_logger("app")
    logger.info("application_starting", version=settings.APP_VERSION)

    # Verify database connectivity on startup
    db_check = DatabaseHealthCheck()
    db_result = await db_check.check()
    if db_result["status"] == "connected":
        logger.info("database_connected")
    else:
        logger.warning("database_unavailable", error=db_result.get("error"))

    # Register domain event handlers
    from backend.core.event_handlers import register_sync_handlers
    from backend.core.domain_events import get_event_bus
    register_sync_handlers(get_event_bus())
    logger.info("event_handlers_registered")

    # Run startup health check
    try:
        from backend.scripts.validate_architecture import startup_health_check
        health = await startup_health_check()
        for msg in health:
            logger.info("health_check", check=msg)
    except Exception as e:
        logger.error("startup_health_check_failed", error=str(e))
        # Non-blocking: log but continue (DB may not be available at boot)

    yield  # ── Application running ──

    # ── Shutdown ───────────────────────────────────────────────
    logger.info("application_stopping")


def create_app() -> FastAPI:
    """Factory function to create and configure the FastAPI application."""
    # Configure structured logging first
    configure_logging()

    app = FastAPI(
        title=settings.APP_TITLE,
        version=settings.APP_VERSION,
        description=settings.APP_DESCRIPTION,
        lifespan=lifespan,
    )

    # ── Middleware (order matters: first added = outer) ─────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestContextMiddleware)

    # ── Global error handlers ──────────────────────────────────
    register_error_handlers(app)

    # ── Routes ─────────────────────────────────────────────────
    app.include_router(api_router)
    app.include_router(health_router)

    return app


app = create_app()
