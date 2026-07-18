"""System job management API endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_session
from backend.services.system_job_service import SystemJobService
from backend.core.scheduler import schedule_job

router = APIRouter()


@router.post("")
async def create_job(
    name: str,
    task_type: str,
    priority: int = Query(0),
    trigger: str = Query("once"),
    session: AsyncSession = Depends(get_session),
):
    svc = SystemJobService(session)
    job = await svc.create_job(
        name=name, task_type=task_type, priority=priority, trigger=trigger,
    )
    schedule_job(
        job_id=UUID(job["id"]),
        task_type=task_type,
        payload=job.get("payload"),
        trigger=trigger,
    )
    return job


@router.get("")
async def list_jobs(
    status: str | None = Query(None),
    limit: int = Query(50),
    session: AsyncSession = Depends(get_session),
):
    svc = SystemJobService(session)
    return await svc.list_jobs(status=status, limit=limit)


@router.get("/{job_id}")
async def get_job(job_id: UUID, session: AsyncSession = Depends(get_session)):
    svc = SystemJobService(session)
    job = await svc.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/{job_id}/retry")
async def retry_job(job_id: UUID, session: AsyncSession = Depends(get_session)):
    svc = SystemJobService(session)
    job = await svc.retry_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: UUID, session: AsyncSession = Depends(get_session)):
    svc = SystemJobService(session)
    job = await svc.cancel_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/scheduler/start")
async def start_scheduler():
    from backend.core.scheduler import start_scheduler as _start
    await _start()
    return {"status": "started"}


@router.post("/scheduler/stop")
async def stop_scheduler():
    from backend.core.scheduler import stop_scheduler as _stop
    await _stop()
    return {"status": "stopped"}
