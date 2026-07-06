"""
EntityExtractor — извлечение BusinessEntities из OCR результата.

Input: normalized_document + OCR entities + semantic result
Output: list[BusinessEntity] + list[EntityIdentifier]

NO DB. NO SQL. NO side effects.
"""
from __future__ import annotations

from domain.business_relationship.entity import BusinessEntity, EntityIdentifier
from domain.business_relationship.entity_types import EntityType, IdentifierType
from domain.property.property_identity import PropertyIdentity


class EntityExtractor:
    """Извлекает сущности из OCR и семантического результата."""

    def extract(
        self,
        ocr_entities: dict,
        raw_text: str = "",
        document_id: str = "",
        semantic_type: str = "",
        company_id: str = "",
        company_names: list[str] | None = None,
        person_names: list[str] | None = None,
        vat_numbers: list[str] | None = None,
    ) -> tuple[list[BusinessEntity], list[EntityIdentifier]]:
        """Извлечь сущности из результатов OCR.

        Returns:
            (entities, identifiers) — НЕ persistent, in-memory only
        """
        entities: list[BusinessEntity] = []
        identifiers: list[EntityIdentifier] = []

        # 1. INN → COMPANY
        inns = vat_numbers or []
        for inn in inns:
            if not inn or not inn.strip():
                continue
            normalized = EntityIdentifier.normalize(inn, IdentifierType.INN)
            if len(normalized) < 10:
                continue
            entity = BusinessEntity(entity_type=EntityType.COMPANY, display_name="")
            idf = EntityIdentifier(
                identifier_type=IdentifierType.INN,
                normalized_value=normalized,
                original_value=inn,
                entity_id=entity.id,
                source_document_id=document_id,
                confidence=0.95,
            )
            entities.append(entity)
            identifiers.append(idf)

        # 2. Company names → COMPANY
        for name in (company_names or []):
            if not name or not name.strip():
                continue
            entity = BusinessEntity(entity_type=EntityType.COMPANY, display_name=name)
            idf = EntityIdentifier(
                identifier_type=IdentifierType.INN,  # INN is the dedup key
                normalized_value=f"name:{name.strip().lower()}",
                original_value=name,
                entity_id=entity.id,
                source_document_id=document_id,
                confidence=0.7,
            )
            entities.append(entity)
            identifiers.append(idf)

        # 3. Person names → PERSON
        for name in (person_names or []):
            if not name or not name.strip():
                continue
            entity = BusinessEntity(entity_type=EntityType.PERSON, display_name=name)
            idf = EntityIdentifier(
                identifier_type=IdentifierType.INN,
                normalized_value=f"person:{name.strip().lower()}",
                original_value=name,
                entity_id=entity.id,
                source_document_id=document_id,
                confidence=0.6,
            )
            entities.append(entity)
            identifiers.append(idf)

        # 4. Cadastre → PROPERTY
        if raw_text:
            cadastral = PropertyIdentity.extract_cadastral(raw_text)
            if cadastral:
                entity = BusinessEntity(entity_type=EntityType.PROPERTY, display_name=cadastral)
                idf = EntityIdentifier(
                    identifier_type=IdentifierType.CADASTRE,
                    normalized_value=cadastral,
                    original_value=cadastral,
                    entity_id=entity.id,
                    source_document_id=document_id,
                    confidence=0.90,
                )
                entities.append(entity)
                identifiers.append(idf)

        # 5. Document reference — extract as DOCUMENT entity (not agreement)
        import re
        if raw_text:
            for line in raw_text.split("\n"):
                line_s = line.strip()
                m = re.search(r"[№#НNn]\s*(?P<num>[\w\-\.]+)", line_s)
                if m:
                    num = m.group("num").strip()
                    if len(num) >= 3 and not num.isdigit():
                        entity = BusinessEntity(entity_type=EntityType.DOCUMENT, display_name=num)
                        idf = EntityIdentifier(
                            identifier_type=IdentifierType.CONTRACT_NUMBER,
                            normalized_value=EntityIdentifier.normalize(num, IdentifierType.CONTRACT_NUMBER),
                            original_value=num,
                            entity_id=entity.id,
                            source_document_id=document_id,
                            confidence=0.85,
                        )
                        entities.append(entity)
                        identifiers.append(idf)
                        break  # only first contract number

        # 6. Amount → no entity, just identifier for future use
        amounts = ocr_entities.get("amount", []) if isinstance(ocr_entities, dict) else []
        for amt in amounts:
            if not amt:
                continue
            idf = EntityIdentifier(
                identifier_type=IdentifierType.INN,  # placeholder — amount is not an entity yet
                normalized_value=f"amount:{amt}",
                original_value=str(amt),
                entity_id="",
                source_document_id=document_id,
                confidence=0.8,
            )

        return entities, identifiers
