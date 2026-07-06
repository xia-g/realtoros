from datetime import datetime
from uuid import UUID

from pydantic import Field

from backend.schemas.base import BaseSchema, BaseResponse


class UserCreate(BaseSchema):
    full_name: str = Field(..., min_length=1, max_length=255)
    email: str | None = None
    phone: str | None = Field(None, max_length=20)
    password: str = Field(..., min_length=6)
    role_id: UUID
    telegram_id: str | None = None
    telegram_username: str | None = None


class UserResponse(BaseResponse):
    role_id: UUID
    status: str
    full_name: str
    phone: str | None = None
    email: str | None = None
    telegram_id: str | None = None
    telegram_username: str | None = None
    last_login: datetime | None = None
