"""
Agreement — business interpretation of document(s).

NOT a Document entity. Agreement is inferred from neutral facts.
In-memory only for v2.0.2. NO DB writes.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from domain.business_relationship.agreement_types import AgreementType


class KnowledgeState(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    HISTORICAL = "historical"


@dataclass
class Agreement:
    """Agreement — интерпретация одного или нескольких документов."""
    agreement_type: AgreementType
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    number: str = ""                          # номер договора
    date: date | None = None                  # дата договора
    currency: str = "RUB"
    amount: Decimal = Decimal("0")
    document_entity_id: str = ""              # ссылка на Document entity
    supporting_document_ids: list[str] = field(default_factory=list)  # другие документы
    knowledge_state: KnowledgeState = KnowledgeState.ACTIVE
    confidence: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def summary(self) -> str:
        return f"{self.agreement_type.value}#{self.number or self.id[:8]}"
