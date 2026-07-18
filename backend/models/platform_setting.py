"""Platform Settings — domain configuration, multi-tenant support.

AP-1: Zero Hardcode — all domains via config.
AP-3: Multi-Tenant Ready — no spcnn.ru binding.
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base

from backend.database import Base
from backend.models.base import UUIDMixin


class PlatformSetting(UUIDMixin, Base):
    """Single platform configuration entry. Key-value with JSONB support."""
    __tablename__ = "platform_settings"

    key: str = Column(String(100), unique=True, nullable=False, index=True)
    value: str = Column(Text, nullable=True)
    value_json: dict = Column(JSONB, nullable=True)
    description: str = Column(String(500), nullable=True)
    category: str = Column(String(50), nullable=False, default="general")
    is_secret: bool = Column(Boolean, nullable=False, default=False)
    version: int = Column(Integer, nullable=False, default=1)
    created_at: datetime = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: datetime = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


DEFAULT_SETTINGS = {
    "primary_domain": {"value": "spcnn.ru", "category": "domains", "description": "Primary domain for all subdomains"},
    "ssl_enabled": {"value": "true", "category": "domains", "description": "Enable HTTPS"},
    "api_subdomain": {"value": "api", "category": "domains", "description": "API subdomain prefix"},
    "crm_subdomain": {"value": "crm", "category": "domains", "description": "CRM subdomain prefix"},
    "admin_subdomain": {"value": "admin", "category": "domains", "description": "Admin subdomain prefix"},
    "executive_subdomain": {"value": "executive", "category": "domains", "description": "Executive dashboard subdomain"},
    "analytics_subdomain": {"value": "analytics", "category": "domains", "description": "Analytics subdomain"},
    "site_title": {"value": "RealtorOS", "category": "branding", "description": "Site title"},
    "site_logo_url": {"value": "", "category": "branding", "description": "Logo URL"},
    "timezone": {"value": "Europe/Moscow", "category": "regional", "description": "Default timezone"},
    "locale": {"value": "ru", "category": "regional", "description": "Default locale"},
    "max_upload_size_mb": {"value": "50", "category": "limits", "description": "Max file upload size"},
    "session_ttl_hours": {"value": "24", "category": "security", "description": "Session TTL"},
    "rate_limit_default": {"value": "100", "category": "security", "description": "Default rate limit per minute"},
    "partition_retention_months": {"value": "12", "category": "data", "description": "Partition retention period"},
}
