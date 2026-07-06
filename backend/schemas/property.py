from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PropertyCreate(BaseModel):
    owner_id: UUID | None = None
    address: str = Field(..., min_length=1)
    property_type: str = "apartment"
    status: str = "active"
    price: float | None = Field(None, ge=0)
    area: float | None = Field(None, ge=0)
    rooms: int | None = Field(None, ge=1)
    description: str | None = None
    created_by: UUID | None = None


class PropertyUpdate(BaseModel):
    address: str | None = None
    property_type: str | None = None
    status: str | None = None
    price: float | None = None
    area: float | None = None
    rooms: int | None = None
    description: str | None = None


class PropertyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    owner_id: UUID | None = None
    address: str
    property_type: str
    status: str
    price: float | None = None
    area: float | None = None
    rooms: int | None = None
    description: str | None = None
    created_by: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
