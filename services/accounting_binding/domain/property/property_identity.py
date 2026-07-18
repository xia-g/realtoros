"""
Property Identity — value object.

Определяет недвижимость как бизнес-сущность.
Не привязан к Deal Resolution — используется всеми доменами.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256
from typing import ClassVar


@dataclass(frozen=True)
class PropertyIdentity:
    """Идентичность объекта недвижимости.

    Приоритет идентификации:
      1. cadastral_number (уникальный, неизменяемый)
      2. normalized_address
      3. остальные характеристики (area, floor, object_type)

    Immutable — после создания не меняется.
    """
    cadastral_number: str = ""
    normalized_address: str = ""
    area: float = 0.0
    floor: int = 0
    object_type: str = ""  # apartment, commercial, land, house, parking, ...

    CADASTRAL_PATTERN: ClassVar[re.Pattern] = re.compile(r"\d{2,3}:\d{2}:\d{6,7}:\d+")

    @property
    def is_valid(self) -> bool:
        """Хотя бы один идентификатор должен быть."""
        return bool(self.cadastral_number or self.normalized_address)

    @property
    def identity_hash(self) -> str:
        """Детерминированный хеш идентичности."""
        raw = f"{self.cadastral_number}|{self.normalized_address}|{self.area}|{self.floor}"
        return sha256(raw.encode("utf-8")).hexdigest()[:16]

    @classmethod
    def extract_cadastral(cls, text: str) -> str:
        """Извлечь кадастровый номер из текста."""
        m = cls.CADASTRAL_PATTERN.search(text)
        return m.group(0) if m else ""

    @classmethod
    def normalize_address(cls, address: str) -> str:
        """Нормализовать адрес: привести к единому формату."""
        if not address:
            return ""
        addr = address.lower().strip()
        # Убрать лишние пробелы
        addr = re.sub(r"\s+", " ", addr)
        # Нормализовать сокращения
        replacements = {
            "г.": "город", "г ": "город ",
            "ул.": "улица", "ул ": "улица ",
            "пр.": "проспект", "пр ": "проспект ",
            "д.": "дом", "д ": "дом ",
            "кв.": "квартира", "кв ": "квартира ",
            "стр.": "строение", "стр ": "строение ",
            "пом.": "помещение", "пом ": "помещение ",
            "лит.": "литера", "лит ": "литера ",
            "наб.": "набережная", "наб ": "набережная ",
            "пер.": "переулок", "пер ": "переулок ",
        }
        for old, new in replacements.items():
            addr = addr.replace(old, new)
        return addr.strip()

    def similarity_to(self, other: PropertyIdentity) -> float:
        """Схожесть двух объектов недвижимости (0.0-1.0)."""
        if not self.is_valid or not other.is_valid:
            return 0.0

        score = 0.0
        total = 0

        # Cadastral: exact match = 1.0, otherwise 0
        if self.cadastral_number and other.cadastral_number:
            total += 1
            if self.cadastral_number == other.cadastral_number:
                score += 1.0

        # Address: fuzzy match
        if self.normalized_address and other.normalized_address:
            total += 0.5
            s_addr = PropertyIdentity.normalize_address(self.normalized_address)
            o_addr = PropertyIdentity.normalize_address(other.normalized_address)
            if s_addr == o_addr:
                score += 0.5
            elif len(set(s_addr.split()) & set(o_addr.split())) / max(len(set(s_addr.split())), 1) > 0.7:
                score += 0.3

        # Area: approximate match (±10%)
        if self.area > 0 and other.area > 0:
            total += 0.3
            ratio = min(self.area, other.area) / max(self.area, other.area)
            if ratio >= 0.9:
                score += 0.3

        return score / total if total > 0 else 0.0
