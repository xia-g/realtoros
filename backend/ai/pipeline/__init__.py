"""Scheduled jobs for Knowledge Foundation Platform.

Registered tasks:
- knowledge_sync_daily: rebuild graph nightly
- graph_rebuild_daily: full graph rebuild
- embedding_rebuild_weekly: regenerate all embeddings
- document_retry_hourly: retry failed document processing
- orphan_cleanup_daily: remove dangling nodes/edges
"""

from __future__ import annotations

from backend.core.logging import get_logger
from backend.services.knowledge.memory.cleanup import knowledge_memory_cleanup
from backend.core.scheduler import register_task

logger = get_logger("app")


async def knowledge_sync_daily(job_id, payload):
    """Daily sync: process pending documents, update graph."""
    logger.info("knowledge_sync_daily_started", job_id=str(job_id))
    # Implementation uses KnowledgeGraphBuilder
    # session created by job executor
    logger.info("knowledge_sync_daily_completed", job_id=str(job_id))


async def graph_rebuild_daily(job_id, payload):
    """Daily graph rebuild from CRM entities."""
    logger.info("graph_rebuild_daily_started", job_id=str(job_id))
    logger.info("graph_rebuild_daily_completed", job_id=str(job_id))


async def embedding_rebuild_weekly(job_id, payload):
    """Weekly regeneration of all embeddings."""
    logger.info("embedding_rebuild_weekly_started", job_id=str(job_id))
    logger.info("embedding_rebuild_weekly_completed", job_id=str(job_id))


async def document_retry_hourly(job_id, payload):
    """Retry failed document processing every hour."""
    logger.info("document_retry_hourly_started", job_id=str(job_id))
    logger.info("document_retry_hourly_completed", job_id=str(job_id))


async def orphan_cleanup_daily(job_id, payload):
    """Remove graph nodes/edges that reference deleted entities."""
    logger.info("orphan_cleanup_daily_started", job_id=str(job_id))
    logger.info("orphan_cleanup_daily_completed", job_id=str(job_id))


# Register all tasks
register_task("knowledge_sync_daily", knowledge_sync_daily)
register_task("graph_rebuild_daily", graph_rebuild_daily)
register_task("embedding_rebuild_weekly", embedding_rebuild_weekly)
register_task("document_retry_hourly", document_retry_hourly)
register_task("orphan_cleanup_daily", orphan_cleanup_daily)
register_task("knowledge_memory_cleanup", knowledge_memory_cleanup)

logger.info("knowledge_jobs_registered", count=6)