"""Infrastructure package exports."""
from infrastructure.exceptions import (
    InfrastructureError,
    StoreError,
    ConnectionError,
    SerializationError,
    ConfigurationError,
    StrategyError,
    TransactionError,
)
from infrastructure.configuration import AdapterConfiguration, StoreType, StrategyType
from infrastructure.memory_store import MemoryProjectionStore
from infrastructure.memory_strategy import InMemoryExecutionStrategy
from infrastructure.projection_codec import ProjectionCodec, ProjectionData
from infrastructure.connection_provider import ConnectionProvider, TransactionManager
from infrastructure.composition_root import (
    ProjectionStoreFactory,
    ExecutionStrategyFactory,
    KnowledgeQueryEngine,
)

__all__ = [
    "InfrastructureError",
    "StoreError",
    "ConnectionError",
    "SerializationError",
    "ConfigurationError",
    "StrategyError",
    "TransactionError",
    "AdapterConfiguration",
    "StoreType",
    "StrategyType",
    "MemoryProjectionStore",
    "InMemoryExecutionStrategy",
    "ProjectionCodec",
    "ProjectionData",
    "ConnectionProvider",
    "TransactionManager",
    "ProjectionStoreFactory",
    "ExecutionStrategyFactory",
    "KnowledgeQueryEngine",
]
