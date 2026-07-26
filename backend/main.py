"""FastAPI application entry point.

Runtime foundation:
  - Structlog structured logging
  - Request context middleware
  - Global error handlers
  - Health check endpoints
  - Startup validation
"""

from __future__ import annotations

import asyncio
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

    # Register domain event handlers (single point, P8 fix)
    from backend.core.event_registry import ensure_event_registry
    ensure_event_registry()
    logger.info("event_handlers_registered")

    # ── Start Event Publisher background task (Stream 3) ───────
    publisher = None
    try:
        from backend.infrastructure.event_publisher import EventPublisher
        publisher = EventPublisher(
            dsn=settings.DATABASE_SYNC_URL,
            poll_interval=1.0,
            batch_size=50,
        )
        # Register GraphSync consumer (migrated to IntegrationEvent)
        from backend.core.event_handlers import graph_sync_consumer
        publisher.register_consumer("document.ready", graph_sync_consumer)
        publisher.register_consumer("document.created", graph_sync_consumer)
        publisher.register_consumer("document.deleted", graph_sync_consumer)
        publisher.register_consumer("client.created", graph_sync_consumer)
        publisher.register_consumer("client.updated", graph_sync_consumer)
        publisher.register_consumer("client.deleted", graph_sync_consumer)
        publisher.register_consumer("property.created", graph_sync_consumer)
        publisher.register_consumer("property.updated", graph_sync_consumer)
        publisher.register_consumer("property.deleted", graph_sync_consumer)
        publisher.register_consumer("deal.created", graph_sync_consumer)
        publisher.register_consumer("deal.updated", graph_sync_consumer)
        publisher.register_consumer("deal.deleted", graph_sync_consumer)
        publisher.register_consumer("lead.converted", graph_sync_consumer)
        publisher.register_consumer("lead.merged", graph_sync_consumer)
        app.state.event_publisher = publisher
        app.state.publisher_task = asyncio.create_task(publisher.start())
        logger.info("event_publisher_started")
    except Exception as e:
        logger.warning("event_publisher_start_failed", error=str(e))
        app.state.event_publisher = None
        app.state.publisher_task = None

    # ── Knowledge Runtime Bootstrap ────────────────────────────
    try:
        from infrastructure.knowledge_persistence.postgresql_knowledge_revision_repository import (
            PostgreSQLKnowledgeRevisionRepository,
        )
        from infrastructure.knowledge_persistence.postgresql_projection_store import (
            PostgreSQLProjectionStore,
        )
        from application.knowledge_persistence.integrator import (
            KnowledgeRuntimeIntegrator,
        )

        dsn = settings.DATABASE_SYNC_URL
        revision_repository = PostgreSQLKnowledgeRevisionRepository(dsn=dsn)
        projection_store = PostgreSQLProjectionStore(dsn=dsn)
        app.state.integrator = KnowledgeRuntimeIntegrator(
            revision_repository=revision_repository,
            projection_store=projection_store,
        )
        logger.info(
            "knowledge_runtime_bootstrapped dsn=%s",
            dsn.replace(dsn[dsn.find(":")+1:dsn.rfind("@")], "***") if "@" in dsn else dsn,
        )
    except Exception as e:
        logger.warning("knowledge_runtime_bootstrap_failed", error=str(e))
        app.state.integrator = None

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
    if hasattr(app.state, "publisher_task") and app.state.publisher_task:
        if hasattr(app.state, "event_publisher") and app.state.event_publisher:
            await app.state.event_publisher.stop()
        app.state.publisher_task.cancel()
        try:
            await app.state.publisher_task
        except asyncio.CancelledError:
            pass
        logger.info("event_publisher_stopped")


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
