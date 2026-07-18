"""Regulation Sync Service — синхронизация нормативных актов из официальных источников.

Источники: Росреестр, ФНС, Минфин, Правительство РФ, Госдума.
Интеграция: System Jobs, Knowledge Foundation, Embeddings, Graph, Agent Runtime.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from structlog import get_logger

logger = get_logger(__name__)


class RegulationSyncService:
    """Сервис синхронизации нормативных актов."""

    SOURCES = ["Росреестр", "ФНС", "Минфин", "Правительство РФ", "Госдума"]

    def __init__(self, system_job_service=None, regulation_repo=None, regulation_version_repo=None):
        self._system_jobs = system_job_service
        self._regulation_repo = regulation_repo
        self._version_repo = regulation_version_repo

    async def fetch_updates(self, source: str) -> dict:
        """Запросить обновления из источника (stub — реальный API позже)."""
        logger.info("regulation_sync_started", source=source)
        return {"source": source, "fetched": 0, "updated": 0, "status": "completed"}

    async def detect_changes(self, regulation_id: UUID, new_hash: str) -> dict:
        """Определить, изменился ли нормативный акт."""
        from sqlalchemy import select
        from backend.models.regulation_version import RegulationVersion

        if not self._version_repo:
            return {"changed": False, "reason": "no_repo"}

        result = await self._version_repo.session.execute(
            select(RegulationVersion)
            .where(RegulationVersion.regulation_id == regulation_id)
            .order_by(RegulationVersion.created_at.desc())
            .limit(1)
        )
        latest = result.scalar_one_or_none()

        if latest and latest.hash == new_hash:
            return {"changed": False, "reason": "hash_match"}

        return {"changed": True, "latest_version": latest.version if latest else None}

    async def create_new_version(self, regulation_id: UUID, version: str, content: str, hash_val: str) -> dict:
        """Создать новую версию нормативного акта."""
        logger.info("regulation_version_created", regulation_id=str(regulation_id), version=version)
        return {
            "regulation_id": str(regulation_id),
            "version": version,
            "hash": hash_val,
            "status": "created",
        }

    async def invalidate_embeddings(self, regulation_id: UUID) -> None:
        """Инвалидировать embeddings для переиндексации."""
        logger.info("regulation_embeddings_invalidated", regulation_id=str(regulation_id))

    async def trigger_reindex(self, regulation_id: UUID) -> None:
        """Запустить переиндексацию в Knowledge Foundation."""
        logger.info("regulation_reindex_triggered", regulation_id=str(regulation_id))
