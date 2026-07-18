"""
Infrastructure Composition Root — wires adapters to protocols.

Single place where concrete implementations are chosen.
No other module in the application should instantiate adapters.
"""
from __future__ import annotations

from typing import Optional

from query_engine.knowledge_query_engine import KnowledgeQueryEngine as BaseEngine
from query_engine.execution_strategy import ExecutionStrategy
from projection.projection_query_service import ProjectionQueryService
from projection.projection_store import ProjectionStore

from infrastructure.memory_store import MemoryProjectionStore
from infrastructure.memory_strategy import InMemoryExecutionStrategy
from infrastructure.configuration import AdapterConfiguration, StoreType, StrategyType
from infrastructure.exceptions import ConfigurationError


class ProjectionStoreFactory:
    """Фабрика для создания ProjectionStore по конфигурации."""

    @staticmethod
    def create(config: AdapterConfiguration) -> ProjectionStore:
        """Create the appropriate store based on configuration."""
        if config.store_type == StoreType.MEMORY:
            return MemoryProjectionStore()
        elif config.store_type == StoreType.POSTGRESQL:
            raise ConfigurationError("PostgreSQL store not implemented in v2.1")
        elif config.store_type == StoreType.NEO4J:
            raise ConfigurationError("Neo4j store not implemented in v2.1")
        elif config.store_type == StoreType.ELASTIC:
            raise ConfigurationError("Elastic store not implemented in v2.1")
        else:
            raise ConfigurationError(f"Unknown store type: {config.store_type}")


class ExecutionStrategyFactory:
    """Фабрика для создания ExecutionStrategy по конфигурации."""

    @staticmethod
    def create(
        config: AdapterConfiguration,
        query_service: ProjectionQueryService,
    ) -> ExecutionStrategy:
        """Create the appropriate strategy based on configuration."""
        if config.strategy_type == StrategyType.IN_MEMORY:
            return InMemoryExecutionStrategy(query_service)
        elif config.strategy_type == StrategyType.POSTGRESQL:
            raise ConfigurationError("PostgreSQL strategy not implemented in v2.1")
        elif config.strategy_type == StrategyType.NEO4J:
            raise ConfigurationError("Neo4j strategy not implemented in v2.1")
        elif config.strategy_type == StrategyType.ELASTIC:
            raise ConfigurationError("Elastic strategy not implemented in v2.1")
        else:
            raise ConfigurationError(f"Unknown strategy type: {config.strategy_type}")


class KnowledgeQueryEngine(BaseEngine):
    """Engine with dependency injection via Composition Root.

    Wires the concrete adapter implementations to the abstract Engine.
    This is the ONLY place where concrete adapter classes are imported.
    """

    def __init__(
        self,
        config: Optional[AdapterConfiguration] = None,
        store: Optional[ProjectionStore] = None,
        query_service: Optional[ProjectionQueryService] = None,
    ) -> None:
        if config is None:
            config = AdapterConfiguration()

        if store is None:
            store = ProjectionStoreFactory.create(config)

        if query_service is None:
            query_service = ProjectionQueryService(store)

        if config is not None:
            strategy = ExecutionStrategyFactory.create(config, query_service)
        else:
            strategy = InMemoryExecutionStrategy(query_service)

        super().__init__(strategy=strategy)
