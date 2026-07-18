"""Health check endpoints.

Provides liveness, readiness, database connectivity, and version info.
"""

from __future__ import annotations

from fastapi import APIRouter

from backend.config import settings
from backend.core.observability import HealthService

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """Basic health check with RC1 status."""
    return {
        "status": "ok",
        "version": "1.0.0-rc1",
        "release": "RC1",
        "feature_freeze": True,
        "architecture_freeze": True,
        "migration_head": "034_control_plane_schema",
    }


@router.get("/health/live")
async def liveness_check():
    """Liveness probe — always returns 200 if the process is running."""
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness_check():
    """Readiness probe — verifies database connectivity."""
    result = await HealthService.check_all()
    return result


@router.get("/version")
async def version_info():
    """Application version info."""
    return {
        "version": settings.APP_VERSION,
        "title": settings.APP_TITLE,
        "description": settings.APP_DESCRIPTION,
    }
