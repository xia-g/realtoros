"""Task management API endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_session
from backend.schemas.task import TaskCreate, TaskUpdate, TaskResponse
from backend.services.task_service import TaskService

router = APIRouter()


@router.post("", response_model=TaskResponse)
async def create_task(body: TaskCreate, session: AsyncSession = Depends(get_session)):
    svc = TaskService(session)
    return await svc.create_task(**body.model_dump(exclude_none=True))


@router.get("", response_model=list[TaskResponse])
async def list_tasks(session: AsyncSession = Depends(get_session)):
    svc = TaskService(session)
    tasks, _ = await svc.repo.list(page=1, page_size=100)
    return tasks


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: UUID, session: AsyncSession = Depends(get_session)):
    svc = TaskService(session)
    task = await svc.repo.get(task_id)
    if task is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(task_id: UUID, body: TaskUpdate, session: AsyncSession = Depends(get_session)):
    svc = TaskService(session)
    task = await svc.repo.update(task_id, **body.model_dump(exclude_none=True))
    if task is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.delete("/{task_id}", status_code=204)
async def delete_task(task_id: UUID, session: AsyncSession = Depends(get_session)):
    svc = TaskService(session)
    await svc.archive_task(task_id)


@router.post("/{task_id}/complete", response_model=TaskResponse)
async def complete_task(task_id: UUID, completed_by: UUID, session: AsyncSession = Depends(get_session)):
    svc = TaskService(session)
    return await svc.complete_task(task_id, completed_by)


@router.post("/{task_id}/reopen", response_model=TaskResponse)
async def reopen_task(task_id: UUID, session: AsyncSession = Depends(get_session)):
    svc = TaskService(session)
    return await svc.reopen_task(task_id)
