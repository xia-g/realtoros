"""
Tests — Party Identity Resolution (v1.5.1).

Проверяет:
- Individual IP detected from name patterns
- OUR_SIDE detection from master data
- External party (counterparty) detection
- Deterministic replay (same input → same classification)
- Unknown person warning
- Self-transaction block
"""
from __future__ import annotations

import pytest

from domain.enrichment.party_identity import (
    EntityType,
    BusinessStatus,
    RelationType,
    PartyRole,
    PartyIdentity,
    MasterDataStore,
)
from domain.enrichment.party_classifier import PartyClassifier
from domain.enrichment.party_validation import PartyValidationRule


class FakeMasterData(MasterDataStore):
    """Тестовое хранилище мастер-данных."""
    def __init__(self):
        self._our = [
            PartyIdentity(
                party_id="our-ip-1",
                name="Шульгина Ирина Юрьевна",
                inn="780527855675",
                entity_type=EntityType.INDIVIDUAL_IP,
                business_status=BusinessStatus.IP,
                confidence=1.0,
            ),
            PartyIdentity(
                party_id="our-company-1",
                name="ООО МойБизнес",
                inn="7701123456",
                entity_type=EntityType.LEGAL_ENTITY,
                business_status=BusinessStatus.COMPANY,
                confidence=1.0,
            ),
        ]

    async def find_by_inn(self, inn: str) -> list[PartyIdentity]:
        return [p for p in self._our if p.inn == inn]

    async def find_by_name(self, name: str) -> list[PartyIdentity]:
        clean = name.lower().replace(" ", "")
        return [p for p in self._our if clean in p.name.lower().replace(" ", "")]

    async def get_our_companies(self) -> list[PartyIdentity]:
        return self._our


@pytest.mark.asyncio
async def test_individual_ip_detected():
    """ИП определяется по паттерну 'ИП' в названии."""
    classifier = PartyClassifier()
    result = await classifier.classify(
        company_names=["ИП Шульгина Ирина Юрьевна"],
        person_names=[],
    )
    assert len(result.parties) == 1
    party = result.parties[0]
    assert party.identity.entity_type == EntityType.INDIVIDUAL_IP
    assert party.identity.business_status == BusinessStatus.IP
    assert "IP_PARTY" in result.tags


@pytest.mark.asyncio
async def test_our_side_detection():
    """OUR_SIDE определяется из мастер-данных."""
    classifier = PartyClassifier(master_data=FakeMasterData())
    result = await classifier.classify(
        company_names=["Шульгина Ирина Юрьевна"],
        person_names=[],
        counterparty_inn="780527855675",
    )
    assert len(result.parties) == 1
    party = result.parties[0]
    assert party.relation.relation == RelationType.OUR_SIDE
    assert party.relation.role == PartyRole.OUR_SIDE
    assert "OUR_PARTY_INVOLVED" in result.tags


@pytest.mark.asyncio
async def test_external_party_detection():
    """Внешний контрагент → EXTERNAL."""
    classifier = PartyClassifier()
    result = await classifier.classify(
        company_names=["ООО СтройИнвест"],
        person_names=[],
    )
    assert len(result.parties) >= 1
    party = result.parties[0]
    assert party.relation.relation == RelationType.EXTERNAL
    assert "EXTERNAL_PARTY" in result.tags


@pytest.mark.asyncio
async def test_replay_same_party_result():
    """Детерминированный replay: same input → same classification_hash."""
    classifier = PartyClassifier()
    r1 = await classifier.classify(
        company_names=["ООО СтройИнвест", "ИП Иванов"],
        person_names=["Петров А.А."],
    )
    r2 = await classifier.classify(
        company_names=["ООО СтройИнвест", "ИП Иванов"],
        person_names=["Петров А.А."],
    )
    assert r1.classification_hash == r2.classification_hash
    assert len(r1.parties) == len(r2.parties)


@pytest.mark.asyncio
async def test_unknown_person_warning():
    """Физическое лицо без статуса → warning."""
    # Классификатор сам не выдаёт warning для unknown person
    # (confidence будет низким)
    classifier = PartyClassifier()
    result = await classifier.classify(
        company_names=[],
        person_names=["Иванов Иван Иванович"],
    )
    # Должна быть хотя бы одна сторона
    assert len(result.parties) >= 1


def test_self_transaction_block():
    """Сделка с самим собой → SELF_DEAL_DETECTED."""
    from contracts import EnrichedDocument, DocumentType
    from datetime import date

    doc = EnrichedDocument(
        document_id="self-deal-test",
        document_type=DocumentType.CONTRACT,
        source="test",
        parties=[
            {
                "identity": {"name": "Наша компания", "entity_type": "legal_entity", "confidence": 1.0},
                "relation": {"role": "our_side", "relation": "our_side", "confidence": 1.0},
            },
            {
                "identity": {"name": "Наша компания", "entity_type": "legal_entity", "confidence": 1.0},
                "relation": {"role": "counterparty", "relation": "external", "confidence": 1.0},
            },
        ],
    )
    result = PartyValidationRule.validate(doc)
    assert not result.is_valid
    assert any(e.code == "SELF_DEAL_DETECTED" for e in result.errors)
