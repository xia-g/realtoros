"""System job repository — CRUD and status management."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update

from backend.models.system_job import SystemJob
from backend.repositories.base import GenericRepository


class SystemJobRepository(GenericRepository[SystemJob]):
    def __init__(self, session):
        super().__init__(session, SystemJob)

    async def get_pending(self, task_type: str | None = None, limit: int = 20) -> list[SystemJob]:
        stmt = (
            select(SystemJob)
            .where(SystemJob.status == "pending")
            .order_by(SystemJob.priority.desc(), SystemJob.created_at.asc())
            .limit(limit)
        )
        if task_type:
            stmt = stmt.where(SystemJob.task_type == task_type)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def mark_running(self, job_id: UUID) -> SystemJob | None:
        stmt = update(SystemJob).where(SystemJob.id == job_id).values(
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        await self.session.execute(stmt)
        await self.session.flush()
        return await self.get(job_id)

    async def mark_completed(self, job_id: UUID, result_data: dict | None = None) -> SystemJob | None:
        stmt = update(SystemJob).where(SystemJob.id == job_id).values(
            status="completed",
            completed_at=datetime.now(timezone.utc),
            result=result_data,
        )
        await self.session.execute(stmt)
        await self.session.flush()
        return await self.get(job_id)

    async def mark_failed(self, job_id: UUID, error: str) -> SystemJob | None:
        stmt = update(SystemJob).where(SystemJob.id == job_id).values(
            status="failed",
            completed_at=datetime.now(timezone.utc),
            error_message=error,
        )
        await self.session.execute(stmt)
        await self.session.flush()
        return await self.get(job_id)

    async def increment_retry(self, job_id: UUID) -> SystemJob | None:
        job = await self.get(job_id)
        if job is None:
            return None
        new_retry = job.retry_count + 1
        if new_retry >= job.max_retries:
            return await self.mark_failed(job_id, f"Max retries ({job.max_retries}) exceeded")
        stmt = update(SystemJob).where(SystemJob.id == job_id).values(
            retry_count=new_retry,
            status="pending",
        )
        await self.session.execute(stmt)
        await self.session.flush()
        return await self.get(job_id)
