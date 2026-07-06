"""Task service — lifecycle management and assignment."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from backend.core.exceptions import NotFoundError, ValidationError
from backend.core.logging import get_logger
from backend.models.task import Task
from backend.repositories import TaskRepository

logger = get_logger("app")


class TaskService:
    def __init__(self, session, task_repository: TaskRepository | None = None):
        self.session = session
        self.repo = task_repository or TaskRepository(session)

    async def create_task(
        self,
        *,
        title: str,
        description: str | None = None,
        task_type: str = "general",
        status: str = "new",
        priority: str = "medium",
        assigned_to: UUID | None = None,
        client_id: UUID | None = None,
        deal_id: UUID | None = None,
        property_id: UUID | None = None,
        created_by: UUID | None = None,
        **extra,
    ) -> Task:
        if not title or not title.strip():
            raise ValidationError(message="Task title is required")

        task = await self.repo.create(
            title=title,
            description=description,
            task_type=task_type,
            status=status,
            priority=priority,
            assigned_to=assigned_to,
            client_id=client_id,
            deal_id=deal_id,
            property_id=property_id,
            created_by=created_by,
            **extra,
        )
        logger.info("task_created", task_id=str(task.id), title=title)
        return task

    async def assign_task(self, task_id: UUID, user_id: UUID) -> Task:
        task = await self.repo.update(task_id, assigned_to=user_id)
        if task is None:
            raise NotFoundError(message=f"Task {task_id} not found")
        task.status = "in_progress"
        await self.session.flush()
        logger.info("task_assigned", task_id=str(task_id), user_id=str(user_id))
        return task

    async def complete_task(self, task_id: UUID, completed_by: UUID) -> Task:
        task = await self.repo.get(task_id)
        if task is None:
            raise NotFoundError(message=f"Task {task_id} not found")

        task.status = "completed"
        task.completed_by = completed_by
        task.completed_at = datetime.now(timezone.utc)
        await self.session.flush()
        logger.info("task_completed", task_id=str(task_id))
        return task

    async def reopen_task(self, task_id: UUID) -> Task:
        task = await self.repo.get(task_id)
        if task is None:
            raise NotFoundError(message=f"Task {task_id} not found")
        task.status = "in_progress"
        task.completed_by = None
        task.completed_at = None
        await self.session.flush()
        logger.info("task_reopened", task_id=str(task_id))
        return task

    async def archive_task(self, task_id: UUID) -> None:
        success = await self.repo.delete(task_id)
        if not success:
            raise NotFoundError(message=f"Task {task_id} not found")
        logger.info("task_archived", task_id=str(task_id))
