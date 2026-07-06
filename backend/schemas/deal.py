from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DealCreate(BaseModel):
    property_id: UUID | None = None
    deal_type: str = "buy"
    status: str = "negotiation"
    created_by: UUID | None = None
    participants: list[UUID] = Field(..., min_length=1)


class DealUpdate(BaseModel):
    deal_type: str | None = None
    status: str | None = None
    property_id: UUID | None = None


class DealResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    property_id: UUID | None = None
    deal_type: str
    status: str
    created_by: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
