"""Infrastructure custom exceptions."""
from __future__ import annotations


class InfrastructureError(Exception):
    """Base infrastructure error."""


class StoreError(InfrastructureError):
    """Projection store operation failed."""


class ConnectionError(InfrastructureError):
    """Storage connection failed."""


class SerializationError(InfrastructureError):
    """Projection serialization/deserialization failed."""


class ConfigurationError(InfrastructureError):
    """Adapter configuration is invalid."""


class StrategyError(InfrastructureError):
    """Execution strategy failed."""


class TransactionError(InfrastructureError):
    """Transaction operation failed."""
