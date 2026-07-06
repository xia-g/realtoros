"""Knowledge Memory cleanup job — scheduled expiry cleanup.

Registered as system job task_type = "knowledge_memory_cleanup".
Runs every 1 hour via APScheduler.
Deletes expired sessions (cascade deletes messages via FK).
"""

from __future__ import annotations

from uuid import UUID

from backend.core.logging import get_logger
from backend.database import async_session_factory
from backend.services.knowledge.memory.memory_service import MemoryService
from backend.ai.metrics import knowledge_session_expired_total, knowledge_sessions_active

logger = get_logger("knowledge")


async def knowledge_memory_cleanup_handler(job_id: UUID, payload: dict | None = None) -> None:
    """Cleanup expired knowledge memory sessions.

    Deletes sessions where expires_at <= now AND is_active = False.
    Cascade deletes messages via FK.
    """
    logger.info("memory_cleanup_started", job_id=str(job_id))

    async with async_session_factory() as session:
        svc = MemoryService(session)
        deleted = await svc.cleanup_expired()
        await session.commit()

    if deleted > 0:
        knowledge_session_expired_total.inc(deleted)
        knowledge_sessions_active.dec(deleted)

    logger.info("memory_cleanup_completed", job_id=str(job_id), sessions_deleted=deleted)
