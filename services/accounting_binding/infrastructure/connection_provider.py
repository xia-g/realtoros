"""
ConnectionProvider Protocol — abstraction over database connections.

No concrete implementations. Only Protocol.
"""
from __future__ import annotations

from typing import Protocol, Any, Optional


class ConnectionProvider(Protocol):
    """Протокол провайдера соединения с БД.

    Никакой реализации. Только протокол.
    """

    def connect(self) -> Any:
        """Establish connection. Returns connection handle."""
        ...

    def disconnect(self) -> None:
        """Close connection."""
        ...

    @property
    def is_connected(self) -> bool:
        """Check if connection is active."""
        ...


class TransactionManager(Protocol):
    """Протокол управления транзакциями.

    Реализации: PostgreSQL (BEGIN/COMMIT/ROLLBACK),
    Neo4j (tx.run), Elastic (bulk indexing).
    """

    def begin(self) -> None:
        """Start transaction."""
        ...

    def commit(self) -> None:
        """Commit current transaction."""
        ...

    def rollback(self) -> None:
        """Rollback current transaction."""
        ...

    @property
    def in_transaction(self) -> bool:
        """Check if transaction is active."""
        ...
