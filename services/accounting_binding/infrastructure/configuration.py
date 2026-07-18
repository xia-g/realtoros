"""
AdapterConfiguration — declarative configuration for infrastructure adapters.

NO business logic. Only maps AdapterType → concrete implementation class.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional


class StoreType(Enum):
    """Тип хранилища Projection."""
    MEMORY = auto()
    POSTGRESQL = auto()
    NEO4J = auto()
    ELASTIC = auto()


class StrategyType(Enum):
    """Тип стратегии исполнения."""
    IN_MEMORY = auto()
    POSTGRESQL = auto()
    NEO4J = auto()
    ELASTIC = auto()
    HYBRID = auto()


@dataclass(frozen=True)
class AdapterConfiguration:
    """Декларативная конфигурация адаптеров.

    Определяет, какие реализации использовать.
    Не содержит бизнес-логики.
    """
    store_type: StoreType = StoreType.MEMORY
    strategy_type: StrategyType = StrategyType.IN_MEMORY
    connection_string: str = ""
    connection_pool_size: int = 5
    timeout_seconds: int = 30

    # Hybrid mode: map QueryTarget → store type
    target_store_map: tuple[tuple[str, StoreType], ...] = ()
