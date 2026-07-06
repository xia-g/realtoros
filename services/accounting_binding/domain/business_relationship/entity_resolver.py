"""
EntityResolver — in-memory dedup service.

Rule: (identifier_type, normalized_value) is natural key.
If found → use existing Entity.
If not → create new Entity.

NO DB writes. Pure in-memory for v2.0.1.
"""
from __future__ import annotations

from domain.business_relationship.entity import BusinessEntity, EntityIdentifier
from domain.business_relationship.entity_types import EntityType, IdentifierType


class EntityResolver:
    """Разрешает EntityIdentifiers в BusinessEntities с дедупликацией."""

    def __init__(self, known_entities: list[BusinessEntity] | None = None):
        """Инициализация с уже известными сущностями."""
        self._entities: dict[str, BusinessEntity] = {}
        self._by_identifier: dict[tuple[str, str], str] = {}  # (type, value) → entity_id
        if known_entities:
            for e in known_entities:
                self._entities[e.id] = e

    def resolve(
        self,
        identifiers: list[EntityIdentifier],
        entity_type: EntityType | None = None,
        display_name: str = "",
    ) -> tuple[BusinessEntity, list[EntityIdentifier]]:
        """Разрешить сущность: найти существующую или создать новую.

        Returns:
            (entity, list of identifiers — new или существующие)
        """
        # 1. Try to find by any identifier
        best = None
        best_confidence = 0.0
        for idf in identifiers:
            if idf.natural_key in self._by_identifier:
                entity_id = self._by_identifier[idf.natural_key]
                entity = self._entities.get(entity_id)
                if entity and idf.confidence > best_confidence:
                    best = entity
                    best_confidence = idf.confidence

        # 2. Found existing entity — register new identifiers
        if best:
            for idf in identifiers:
                if idf.natural_key not in self._by_identifier:
                    idf.entity_id = best.id
                    self._by_identifier[idf.natural_key] = best.id
            return best, identifiers

        # 3. No existing entity — create new
        guessed_type = self._guess_type(identifiers) if not entity_type else entity_type
        name = display_name or self._guess_name(identifiers)

        new_entity = BusinessEntity(entity_type=guessed_type, display_name=name)
        self._entities[new_entity.id] = new_entity

        for idf in identifiers:
            idf.entity_id = new_entity.id
            self._by_identifier[idf.natural_key] = new_entity.id

        return new_entity, identifiers

    def _guess_type(self, identifiers: list[EntityIdentifier]) -> EntityType:
        """Определить тип сущности по идентификаторам."""
        for idf in identifiers:
            if idf.identifier_type in (IdentifierType.INN, IdentifierType.OGRN):
                return EntityType.COMPANY
            if idf.identifier_type == IdentifierType.EMAIL:
                return EntityType.PERSON
        # Default: company for legal entities with INN
        has_inn = any(idf.identifier_type == IdentifierType.INN for idf in identifiers)
        return EntityType.COMPANY if has_inn else EntityType.PERSON

    def _guess_name(self, identifiers: list[EntityIdentifier]) -> str:
        """Угадать отображаемое имя."""
        # Use original value of the highest-confidence identifier
        best_idf = max(identifiers, key=lambda i: i.confidence)
        return best_idf.original_value or best_idf.normalized_value

    @property
    def entities(self) -> list[BusinessEntity]:
        return list(self._entities.values())
