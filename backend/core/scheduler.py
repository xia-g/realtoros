"""APScheduler integration for system jobs.

Provides:
- schedule_job(): add a job to APScheduler
- start_scheduler(): init and start the scheduler
- job_executor(): generic wrapper to execute SystemJob tasks

Triggers:
- "once": run immediately or at scheduled_at
- "interval": run every N seconds/minutes/hours
- "cron": run at specific times (cron expression)
- "date": run once at specific datetime
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable
from uuid import UUID

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger

from backend.core.logging import get_logger

logger = get_logger("app")

_scheduler: AsyncIOScheduler | None = None
_TASK_REGISTRY: dict[str, Callable] = {}


def register_task(task_type: str, handler: Callable) -> None:
    """Register a handler function for a task_type."""
    _TASK_REGISTRY[task_type] = handler
    logger.info("task_registered", task_type=task_type, handler=handler.__name__)


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


async def start_scheduler() -> None:
    """Initialize and start the APScheduler."""
    sched = get_scheduler()
    if not sched.running:
        sched.start()
        logger.info("scheduler_started")
    else:
        logger.info("scheduler_already_running")


async def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("scheduler_stopped")


def _build_trigger(trigger: str, args: dict | None = None) -> Any:
    """Build an APScheduler trigger from config."""
    args = args or {}
    if trigger == "interval":
        return IntervalTrigger(**args)
    elif trigger == "cron":
        return CronTrigger(**args)
    elif trigger == "date":
        return DateTrigger(**args)
    elif trigger == "once":
        return DateTrigger(run_date=args.get("run_date", datetime.now()))
    return DateTrigger(run_date=datetime.now())


async def execute_job(job_id: UUID, task_type: str, payload: dict | None = None) -> None:
    """Execute a job by task_type using registered handler."""
    handler = _TASK_REGISTRY.get(task_type)
    if handler is None:
        logger.error("no_handler_for_task", task_type=task_type, job_id=str(job_id))
        return
    try:
        logger.info("job_executing", job_id=str(job_id), task_type=task_type)
        await handler(job_id=job_id, payload=payload or {})
        logger.info("job_completed", job_id=str(job_id), task_type=task_type)
    except Exception as e:
        logger.exception("job_failed", job_id=str(job_id), task_type=task_type, error=str(e))


def schedule_job(
    job_id: UUID,
    task_type: str,
    payload: dict | None = None,
    trigger: str = "once",
    trigger_args: dict | None = None,
    job_name: str = "system_job",
) -> str | None:
    """Add a job to APScheduler. Returns APScheduler job ID."""
    sched = get_scheduler()
    trigger_obj = _build_trigger(trigger, trigger_args)

    aps_job = sched.add_job(
        execute_job,
        trigger=trigger_obj,
        args=[job_id, task_type, payload],
        name=job_name,
        misfire_grace_time=300,
        replace_existing=True,
    )
    logger.info(
        "job_scheduled",
        aps_job_id=aps_job.id,
        job_id=str(job_id),
        task_type=task_type,
        trigger=trigger,
    )
    return aps_job.id
