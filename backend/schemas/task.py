from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1)
    description: str | None = None
    task_type: str = "general"
    status: str = "new"
    priority: str = "medium"
    assigned_to: UUID | None = None
    client_id: UUID | None = None
    deal_id: UUID | None = None
    property_id: UUID | None = None
    created_by: UUID | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    priority: str | None = None
    assigned_to: UUID | None = None


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    title: str
    description: str | None = None
    task_type: str
    status: str
    priority: str | None = None
    assigned_to: UUID | None = None
    client_id: UUID | None = None
    deal_id: UUID | None = None
    property_id: UUID | None = None
    created_by: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    completed_at: datetime | None = None
