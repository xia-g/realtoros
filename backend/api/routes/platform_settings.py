"""Platform Settings API — multi-tenant domain configuration."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_session
from backend.models.platform_setting import PlatformSetting, DEFAULT_SETTINGS
from backend.services.domain_config_service import DomainConfig

router = APIRouter(tags=["platform"])


class SettingResponse(BaseModel):
    key: str
    value: str | None
    category: str
    description: str | None


class SettingsUpdate(BaseModel):
    settings: dict[str, str]


@router.get("/settings")
async def get_settings(session: AsyncSession = Depends(get_session)):
    """Get all platform settings."""
    from sqlalchemy import select

    result = await session.execute(select(PlatformSetting))
    rows = result.scalars().all()

    settings = {}
    for row in rows:
        settings[row.key] = row.value

    # Merge defaults for missing keys
    for key, default in DEFAULT_SETTINGS.items():
        if key not in settings:
            settings[key] = default["value"]

    return {"settings": settings, "count": len(settings)}


@router.put("/settings")
async def update_settings(
    body: SettingsUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update platform settings."""
    from sqlalchemy import select

    updated = []
    for key, value in body.settings.items():
        result = await session.execute(
            select(PlatformSetting).where(PlatformSetting.key == key)
        )
        setting = result.scalar_one_or_none()
        if setting:
            setting.value = value
            setting.version += 1
        else:
            setting = PlatformSetting(
                key=key, value=value, category="custom"
            )
            session.add(setting)
        updated.append(key)

    await session.commit()
    return {"updated": updated, "count": len(updated)}


@router.get("/domains")
async def get_domains(session: AsyncSession = Depends(get_session)):
    """Get domain configuration."""
    from sqlalchemy import select

    result = await session.execute(select(PlatformSetting))
    rows = result.scalars().all()
    settings = {row.key: row.value for row in rows if row.value}

    config = DomainConfig.from_settings(settings)
    return {
        "primary_domain": config.primary_domain,
        "ssl_enabled": config.ssl_enabled,
        "urls": {
            "api": config.api_url,
            "crm": config.crm_url,
            "admin": config.admin_url,
            "executive": config.executive_url,
            "analytics": config.analytics_url,
        },
        "subdomains": {
            "api": config.api_subdomain,
            "crm": config.crm_subdomain,
            "admin": config.admin_subdomain,
            "executive": config.executive_subdomain,
            "analytics": config.analytics_subdomain,
        },
    }


@router.get("/health")
async def platform_health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "sprints": "1-8.8",
        "readiness": "production",
    }


@router.get("/version")
async def platform_version():
    """Version info."""
    return {
        "version": "1.0.0",
        "build": "rc-2",
        "sprints": "1-8.8",
        "migrations": 25,
        "tables": 52,
    }
