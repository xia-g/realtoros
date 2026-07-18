from datetime import date, datetime
from uuid import UUID

from pydantic import Field

from backend.schemas.base import BaseSchema, BaseResponse


class DocumentCreate(BaseSchema):
    document_type: str = Field(..., pattern=r"^(contract|passport|extract|deed|receipt|statement|photo|video|report|other)$")
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    file_name: str = Field(..., max_length=255)
    file_path: str = Field(..., max_length=500)
    file_size: int | None = None
    file_hash: str | None = None
    mime_type: str | None = None
    client_id: UUID | None = None
    property_id: UUID | None = None
    deal_id: UUID | None = None
    uploaded_by: UUID
    expiry_date: date | None = None
    notes: str | None = None


class DocumentResponse(BaseResponse):
    document_type: str
    status: str
    title: str
    description: str | None = None
    file_name: str
    file_path: str
    file_size: int | None = None
    file_hash: str | None = None
    mime_type: str | None = None
    client_id: UUID | None = None
    property_id: UUID | None = None
    deal_id: UUID | None = None
    uploaded_by: UUID
    expiry_date: date | None = None
    notes: str | None = None
