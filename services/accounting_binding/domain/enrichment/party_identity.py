"""
Party Identity Resolution Layer.

OCR извлекает: "Шульгина Ирина Юрьевна"
Accounting Binding понимает: INDIVIDUAL_IP, OUR_SIDE, confidence 0.95

НЕ менять: normalized_document, OCR, journal_entry.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Protocol


class EntityType(str, Enum):
    """Тип участника сделки."""
    INDIVIDUAL = "individual"        # Физическое лицо
    INDIVIDUAL_IP = "individual_ip"  # Индивидуальный предприниматель
    LEGAL_ENTITY = "legal_entity"    # Юридическое лицо
    UNKNOWN = "unknown"


class BusinessStatus(str, Enum):
    """Бизнес-статус участника."""
    PERSON = "person"
    IP = "ip"
    COMPANY = "company"
    UNKNOWN = "unknown"


class PartyRole(str, Enum):
    """Роль участника в документе."""
    CLIENT = "client"
    SUPPLIER = "supplier"
    OWNER = "owner"
    AGENT = "agent"
    OUR_SIDE = "our_side"
    COUNTERPARTY = "counterparty"
    UNKNOWN = "unknown"


class RelationType(str, Enum):
    """Тип отношения к нашей стороне."""
    OUR_SIDE = "our_side"          # это мы (наша компания / ИП)
    EXTERNAL = "external"          # внешний участник
    RELATED = "related"            # связанное лицо
    UNKNOWN = "unknown"


class IdentitySource(str, Enum):
    """Источник данных об участнике."""
    OCR = "ocr"
    USER = "user"
    MASTER_DATA = "master_data"
    INFERRED = "inferred"


@dataclass
class PartyIdentity:
    """Идентифицированная сторона сделки."""
    party_id: str = ""
    name: str = ""
    inn: str = ""
    kpp: str = ""
    entity_type: EntityType = EntityType.UNKNOWN
    business_status: BusinessStatus = BusinessStatus.UNKNOWN
    confidence: float = 0.0
    source: IdentitySource = IdentitySource.OCR


@dataclass
class PartyRelation:
    """Отношение участника к нашей стороне."""
    role: PartyRole = PartyRole.UNKNOWN
    relation: RelationType = RelationType.UNKNOWN
    confidence: float = 0.0


@dataclass
class TransactionParty:
    """Участник сделки с идентификацией и отношением."""
    identity: PartyIdentity = field(default_factory=PartyIdentity)
    relation: PartyRelation = field(default_factory=PartyRelation)


class MasterDataStore(Protocol):
    """Хранилище мастер-данных для поиска участников."""
    async def find_by_inn(self, inn: str) -> list[PartyIdentity]: ...
    async def find_by_name(self, name: str) -> list[PartyIdentity]: ...
    async def get_our_companies(self) -> list[PartyIdentity]: ...
