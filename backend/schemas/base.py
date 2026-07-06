from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


# ── Base ──────────────────────────────────────────────────────────

class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class BaseResponse(BaseSchema):
    id: UUID
    created_at: datetime
    updated_at: datetime


# ── Pagination ────────────────────────────────────────────────────

class PaginationParams(BaseModel):
    page: int = 1
    page_size: int = 50


class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
    total_pages: int
