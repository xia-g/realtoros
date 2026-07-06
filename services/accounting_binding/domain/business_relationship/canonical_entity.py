"""
CanonicalEntity, CanonicalProperty, CanonicalAgreement — master data aggregates.

Represent the SINGLE TRUTH for each business entity.
All in-memory for v2.0.3. NO DB writes.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from domain.business_relationship.entity_types import EntityType
from domain.business_relationship.agreement_types import AgreementType
from domain.business_relationship.support_models import Alias, ConfidenceHistory


@dataclass
class CanonicalEntity:
    """Каноническая бизнес-сущность (Person, Company, Government, Bank)."""
    entity_type: EntityType
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    display_name: str = ""
    primary_identifier: str = ""           # INN or equivalent
    aliases: list[Alias] = field(default_factory=list)
    identifiers: list[str] = field(default_factory=list)  # normalized identifier values
    confidence_history: ConfidenceHistory | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def confidence(self) -> float:
        if self.confidence_history:
            return self.confidence_history.current_confidence
        return 0.0

    def add_alias(self, original: str, normalized: str, confidence: float = 0.8, source_doc: str = ""):
        """Добавить альтернативное название."""
        norm = normalized or original
        if not any(a.normalized_value == norm for a in self.aliases):
            self.aliases.append(Alias(
                original_value=original,
                normalized_value=norm,
                confidence=confidence,
                source_document=source_doc,
            ))

    def confirm(self, document_id: str, agreement_id: str = ""):
        """Подтвердить сущность новым документом."""
        if not self.confidence_history:
            self.confidence_history = ConfidenceHistory(entity_id=self.id)
        self.confidence_history.add(document_id, agreement_id)


@dataclass
class CanonicalProperty:
    """Канонический объект недвижимости."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    cadastral_number: str = ""
    normalized_address: str = ""
    area: float = 0.0
    floor: int = 0
    object_type: str = ""
    aliases: list[Alias] = field(default_factory=list)
    confidence_history: ConfidenceHistory | None = None

    @property
    def confidence(self) -> float:
        if self.confidence_history:
            return self.confidence_history.current_confidence
        return 0.0

    def confirm(self, document_id: str, agreement_id: str = ""):
        if not self.confidence_history:
            self.confidence_history = ConfidenceHistory(entity_id=self.id)
        self.confidence_history.add(document_id, agreement_id)


@dataclass
class CanonicalAgreement:
    """Каноническое соглашение (результат Agreement Resolution)."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agreement_id: str = ""                 # ссылка на in-memory Agreement
    agreement_type: AgreementType = AgreementType.UNKNOWN
    number: str = ""
    date: str = ""
    amount: Decimal = Decimal("0")
    participant_entity_ids: list[str] = field(default_factory=list)
    confidence_history: ConfidenceHistory | None = None

    @property
    def confidence(self) -> float:
        if self.confidence_history:
            return self.confidence_history.current_confidence
        return 0.0

    def confirm(self, document_id: str):
        if not self.confidence_history:
            self.confidence_history = ConfidenceHistory(entity_id=self.id)
        self.confidence_history.add(document_id)
