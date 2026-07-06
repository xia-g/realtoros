"""System job service — schedule, execute, and track background tasks."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select as sa_select

from backend.core.logging import get_logger
from backend.models.system_job import SystemJob
from backend.repositories.system_job_repository import SystemJobRepository

logger = get_logger("app")


class SystemJobService:
    def __init__(self, session):
        self.session = session
        self.repo = SystemJobRepository(session)

    async def create_job(
        self,
        name: str,
        task_type: str,
        *,
        priority: int = 0,
        trigger: str = "once",
        trigger_args: dict | None = None,
        payload: dict | None = None,
        max_retries: int = 3,
        scheduled_at: datetime | None = None,
        created_by: UUID | None = None,
    ):
        job = await self.repo.create(
            name=name,
            task_type=task_type,
            status="pending",
            priority=priority,
            trigger=trigger,
            trigger_args=trigger_args or {},
            payload=payload or {},
            max_retries=max_retries,
            scheduled_at=scheduled_at,
            created_by=created_by,
        )
        logger.info("job_created", job_id=str(job.id), task_type=task_type, name=name)
        return self._serialize(job)

    async def get_job(self, job_id: UUID) -> dict | None:
        job = await self.repo.get(job_id)
        return self._serialize(job) if job else None

    async def list_jobs(self, status: str | None = None, limit: int = 50) -> list[dict]:
        stmt = sa_select(SystemJob).order_by(SystemJob.created_at.desc()).limit(limit)
        if status:
            stmt = stmt.where(SystemJob.status == status)
        result = await self.session.execute(stmt)
        return [self._serialize(j) for j in result.scalars().all()]

    async def retry_job(self, job_id: UUID) -> dict | None:
        job = await self.repo.increment_retry(job_id)
        if job is None:
            return None
        logger.info("job_retry", job_id=str(job_id), retry=job.retry_count)
        return self._serialize(job)

    async def cancel_job(self, job_id: UUID) -> dict | None:
        from sqlalchemy import update
        stmt = update(SystemJob).where(SystemJob.id == job_id).values(status="cancelled")
        await self.session.execute(stmt)
        await self.session.flush()
        return await self.get_job(job_id)

    def _serialize(self, job) -> dict:
        return {
            "id": str(job.id),
            "name": job.name,
            "task_type": job.task_type,
            "status": job.status,
            "priority": job.priority,
            "trigger": job.trigger,
            "trigger_args": job.trigger_args,
            "payload": job.payload,
            "result": job.result,
            "error_message": job.error_message,
            "retry_count": job.retry_count,
            "max_retries": job.max_retries,
            "scheduled_at": job.scheduled_at.isoformat() if job.scheduled_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "created_at": job.created_at.isoformat() if job.created_at else None,
        }
