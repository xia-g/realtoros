"""DocumentReadyPayload — формальный контракт payload для document.ready event.

Валидируется при создании IntegrationEvent в EventAdapter.to_integration().
Consumer использует dataclass для type-safe доступа к payload.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True)
class DocumentReadyPayload:
    """Formal contract for document.ready event payload.

    Validated at event creation time in EventAdapter.to_integration().
    Consumer loads document data from DB — payload stays minimal.

    Attributes:
        document_id: UUID документа (обязательный).
        profile: ContractProfile JSONB (опциональный, может быть пустым).
        source: Источник события — всегда "document.ready".
    """

    document_id: UUID
    profile: dict = field(default_factory=dict)
    source: str = "document.ready"
