from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LeadCreate(BaseModel):
    source: str = Field(..., description="Source channel: telegram, avito, cian, etc.")
    source_id: str | None = None
    full_name: str | None = None
    phone: str | None = None
    email: str | None = None
    telegram_id: str | None = None
    interest_type: str = "unknown"
    budget_min: float | None = Field(None, ge=0)
    budget_max: float | None = Field(None, ge=0)
    property_type: str | None = None
    notes: str | None = None
    created_by: UUID | None = None


class LeadUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    email: str | None = None
    interest_type: str | None = None
    budget_min: float | None = None
    budget_max: float | None = None
    property_type: str | None = None
    notes: str | None = None
    priority: str | None = None
    assigned_to: UUID | None = None


class LeadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    source: str
    source_id: str | None = None
    full_name: str | None = None
    phone: str | None = None
    email: str | None = None
    telegram_id: str | None = None
    interest_type: str
    status: str
    priority: str | None = None
    score: float | None = None
    budget_min: float | None = None
    budget_max: float | None = None
    property_type: str | None = None
    assigned_to: UUID | None = None
    client_id: UUID | None = None
    deal_id: UUID | None = None
    created_by: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
