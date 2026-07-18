"""
Party Classifier — определяет кто есть кто в документе.

Поток:
1. OCR entities → raw party names
2. Поиск в мастер-данных (ИНН, название)
3. Определение entity_type (INDIVIDUAL / INDIVIDUAL_IP / LEGAL_ENTITY)
4. Определение relation (OUR_SIDE / EXTERNAL)
5. Детерминировано: same input → same output
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Protocol

from domain.enrichment.party_identity import (
    BusinessStatus,
    EntityType,
    IdentitySource,
    MasterDataStore,
    PartyIdentity,
    RelationType,
    PartyRelation,
    PartyRole,
    TransactionParty,
)


# Паттерны для определения ИП по названию
IP_PATTERNS = [
    r"^ип\s+",
    r"^индивидуальный предприниматель",
    r"^индивидуального предпринимател",
    r"ип\s",
]

# Паттерны для определения ЮЛ
LEGAL_PATTERNS = [
    r"(?:ооо|зао|ао|пао|оао|тко|ичп|чп|сп|тнв)\b",
    r"(?:общество|корпорация|компания|фирма|предприятие)",
]


@dataclass
class PartyClassificationResult:
    """Результат классификации участников."""
    parties: list[TransactionParty] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    classification_hash: str = ""


class PartyClassifier:
    """Классификатор участников сделки.

    Детерминирован: same normalized_document + same master data
    → same party classification.
    """

    def __init__(self, master_data: MasterDataStore | None = None):
        self._master = master_data

    async def classify(
        self,
        company_names: list[str],
        person_names: list[str],
        counterparty_inn: str = "",
        company_id: str = "",
    ) -> PartyClassificationResult:
        """Классифицировать всех участников из документа."""
        parties: list[TransactionParty] = []
        tags: set[str] = set()
        warnings: list[str] = []

        # 1. Получить нашу сторону (our company / IP)
        our_side = await self._get_our_side(company_id)
        # Если company_id не указан, попробовать найти по ИНН
        if our_side is None and counterparty_inn and self._master:
            companies = await self._master.get_our_companies()
            for c in companies:
                if c.inn == counterparty_inn:
                    our_side = c
                    break

        # 2. Обработать компании (юридические лица)
        for name in company_names:
            if not name.strip():
                continue
            party = await self._classify_company(name, our_side, counterparty_inn)
            parties.append(party)
            tags.update(self._tags_for_party(party))

        # 3. Обработать физических лиц
        for name in person_names:
            if not name.strip():
                continue

            # Проверка: не дублирует ли уже добавленную компанию
            if self._is_already_present(parties, name):
                continue

            party = await self._classify_person(name, our_side)
            parties.append(party)
            tags.update(self._tags_for_party(party))

        # 4. Если участников нет — предупреждение
        if not parties:
            warnings.append("Не удалось определить участников сделки")

        # 5. Детерминированный хеш
        classification_hash = self._compute_hash(parties, list(tags))

        return PartyClassificationResult(
            parties=parties,
            tags=sorted(tags),
            warnings=warnings,
            classification_hash=classification_hash,
        )

    async def _classify_company(
        self, name: str, our_side: PartyIdentity | None, counterparty_inn: str
    ) -> TransactionParty:
        """Классифицировать юридическое лицо (с проверкой на ИП в названии)."""
        name_lower = name.lower().strip()

        # Проверка: ИП в названии компании → переклассифицировать как person
        if any(re.search(p, name_lower) for p in IP_PATTERNS):
            return await self._classify_person(name, our_side)

        entity_type = EntityType.LEGAL_ENTITY
        business_status = BusinessStatus.COMPANY

        # Поиск в мастер-данных
        identity = PartyIdentity(
            name=name,
            entity_type=entity_type,
            business_status=business_status,
            confidence=0.6,
            source=IdentitySource.OCR,
        )

        if self._master and counterparty_inn:
            matches = await self._master.find_by_inn(counterparty_inn)
            if matches:
                identity = matches[0]
                identity.source = IdentitySource.MASTER_DATA
                identity.confidence = 0.95

        # Определение отношения
        relation = self._determine_relation(identity, our_side, name)

        return TransactionParty(identity=identity, relation=relation)

    async def _classify_person(
        self, name: str, our_side: PartyIdentity | None
    ) -> TransactionParty:
        """Классифицировать физическое лицо (с проверкой на ИП)."""
        name_lower = name.lower().strip()

        # Проверка паттернов ИП
        is_ip = any(re.search(p, name_lower) for p in IP_PATTERNS)

        if is_ip:
            entity_type = EntityType.INDIVIDUAL_IP
            business_status = BusinessStatus.IP
            confidence = 0.85
        else:
            entity_type = EntityType.INDIVIDUAL
            business_status = BusinessStatus.PERSON
            confidence = 0.7

        identity = PartyIdentity(
            name=name,
            entity_type=entity_type,
            business_status=business_status,
            confidence=confidence,
            source=IdentitySource.OCR,
        )

        # Поиск в мастер-данных (по ФИО)
        if self._master:
            matches = await self._master.find_by_name(name)
            if matches:
                identity = matches[0]
                identity.source = IdentitySource.MASTER_DATA
                identity.confidence = max(confidence, 0.95)

        relation = self._determine_relation(identity, our_side, name)

        return TransactionParty(identity=identity, relation=relation)

    def _determine_relation(
        self, identity: PartyIdentity, our_side: PartyIdentity | None, raw_name: str
    ) -> PartyRelation:
        """Определить отношение участника к нашей стороне."""
        # OUR_SIDE: если совпадает с нашей компанией/ИП
        if our_side and self._is_same_party(identity, our_side, raw_name):
            return PartyRelation(
                role=PartyRole.OUR_SIDE,
                relation=RelationType.OUR_SIDE,
                confidence=0.95,
            )

        # По умолчанию — внешний контрагент
        return PartyRelation(
            role=PartyRole.COUNTERPARTY,
            relation=RelationType.EXTERNAL,
            confidence=0.7,
        )

    async def _get_our_side(self, company_id: str) -> PartyIdentity | None:
        """Получить нашу сторону из мастер-данных."""
        if not self._master:
            return None
        companies = await self._master.get_our_companies()
        for c in companies:
            if c.party_id == company_id or c.inn == company_id:
                return c
        return None

    def _is_same_party(
        self, a: PartyIdentity, b: PartyIdentity, raw_name: str = ""
    ) -> bool:
        """Проверить, что две идентификации относятся к одному лицу."""
        if a.inn and b.inn and a.inn == b.inn:
            return True
        if a.party_id and b.party_id and a.party_id == b.party_id:
            return True
        # По имени (неточное совпадение)
        if raw_name and b.name:
            a_clean = re.sub(r"\s+", "", raw_name.lower())
            b_clean = re.sub(r"\s+", "", b.name.lower())
            return a_clean == b_clean or a_clean in b_clean or b_clean in a_clean
        return False

    def _is_already_present(self, parties: list[TransactionParty], name: str) -> bool:
        """Проверить, не добавлен ли уже участник с таким именем."""
        name_clean = re.sub(r"\s+", "", name.lower())
        for p in parties:
            p_clean = re.sub(r"\s+", "", p.identity.name.lower())
            if p_clean == name_clean or p_clean in name_clean or name_clean in p_clean:
                return True
        return False

    def _tags_for_party(self, party: TransactionParty) -> list[str]:
        """Теги для участника."""
        tags = []
        if party.relation.relation == RelationType.OUR_SIDE:
            tags.append("OUR_PARTY_INVOLVED")
        if party.relation.relation == RelationType.EXTERNAL:
            tags.append("EXTERNAL_PARTY")
        if party.identity.entity_type == EntityType.INDIVIDUAL_IP:
            tags.append("IP_PARTY")
        if party.identity.entity_type == EntityType.INDIVIDUAL:
            tags.append("INDIVIDUAL_PARTY")
        if party.identity.entity_type == EntityType.LEGAL_ENTITY:
            tags.append("LEGAL_ENTITY_PARTY")
        return tags

    def _compute_hash(self, parties: list[TransactionParty], tags: list[str]) -> str:
        """Детерминированный хеш классификации."""
        data = []
        for p in sorted(parties, key=lambda x: x.identity.name):
            data.append(f"{p.identity.name}:{p.identity.entity_type.value}:{p.relation.relation.value}")
        raw = "|".join(data + sorted(tags))
        return hashlib.sha256(raw.encode()).hexdigest()[:16]
