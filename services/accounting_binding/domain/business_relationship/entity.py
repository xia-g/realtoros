"""
BusinessEntity + EntityIdentifier — in-memory models.

Entity: бизнес-сущность (PERSON, COMPANY, PROPERTY, etc.)
EntityIdentifier: как мы находим Entity (INN, CADASTRE, EMAIL, etc.)

UNIQUE natural key: (identifier_type, normalized_value)
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from domain.business_relationship.entity_types import EntityType, IdentifierType


@dataclass
class BusinessEntity:
    """Бизнес-сущность. NOT persistent in v2.0.1."""
    entity_type: EntityType
    display_name: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.utcnow)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BusinessEntity):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)


@dataclass
class EntityIdentifier:
    """Идентификатор сущности. Связывает Entity с реальным значением."""
    identifier_type: IdentifierType
    normalized_value: str
    entity_id: str
    original_value: str = ""
    source_document_id: str = ""
    confidence: float = 1.0
    id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @property
    def natural_key(self) -> tuple[str, str]:
        """Естественный ключ для дедупликации."""
        return (self.identifier_type.value, self.normalized_value)

    @staticmethod
    def normalize(value: str, identifier_type: IdentifierType) -> str:
        """Нормализовать значение для сравнения."""
        v = value.strip()
        if identifier_type == IdentifierType.INN:
            v = "".join(c for c in v if c.isdigit())
            if len(v) > 12:
                v = v[:12]
        elif identifier_type == IdentifierType.PHONE:
            v = "".join(c for c in v if c.isdigit() or c == "+")
            if v.startswith("8"):
                v = "+7" + v[1:]
        elif identifier_type == IdentifierType.EMAIL:
            v = v.lower().strip()
        elif identifier_type == IdentifierType.ADDRESS:
            from domain.property.property_identity import PropertyIdentity
            v = PropertyIdentity.normalize_address(v)
        elif identifier_type == IdentifierType.CONTRACT_NUMBER:
            v = v.strip().upper()
        elif identifier_type == IdentifierType.CADASTRE:
            v = v.strip()
        return v
