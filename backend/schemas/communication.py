from datetime import datetime
from uuid import UUID

from pydantic import Field

from backend.schemas.base import BaseSchema, BaseResponse


class CommunicationCreate(BaseSchema):
    communication_type: str = Field(..., pattern=r"^(call|email|telegram|whatsapp|meeting|site_message|note)$")
    direction: str = Field(..., pattern=r"^(incoming|outgoing)$")
    client_id: UUID | None = None
    deal_id: UUID | None = None
    subject: str | None = Field(None, max_length=255)
    content: str
    duration: int | None = None
    contact: str | None = Field(None, max_length=255)
    assigned_to: UUID | None = None
    is_important: bool = False
    tags: list[str] | None = None
    created_by: UUID


class CommunicationResponse(BaseResponse):
    communication_type: str
    direction: str
    client_id: UUID | None = None
    deal_id: UUID | None = None
    subject: str | None = None
    content: str
    duration: int | None = None
    contact: str | None = None
    assigned_to: UUID | None = None
    is_important: bool
    tags: list[str] | None = None
    created_by: UUID
