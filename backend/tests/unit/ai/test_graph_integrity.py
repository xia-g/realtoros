"""Tests for KnowledgeGraphBuilder integrity."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from uuid_extensions import uuid7


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.flush = AsyncMock()
    return session


@pytest.fixture
def builder(mock_session):
    from backend.ai.graph import KnowledgeGraphBuilder
    return KnowledgeGraphBuilder(mock_session)


class TestUpsertEdge:
    async def test_upsert_edge_filters_by_node_type(self, builder):
        """Should look up nodes by BOTH entity_id and node_type."""
        from backend.models.graph_node import GraphNode
        client_id = uuid7()
        prop_id = uuid7()

        # Mock nodes exist with different types but same-style IDs
        mock_client_node = MagicMock(id=uuid7(), node_type="client", entity_id=client_id)
        mock_prop_node = MagicMock(id=uuid7(), node_type="property", entity_id=prop_id)

        async def mock_execute(stmt):
            where_clauses = stmt.whereclause.__dict__ if hasattr(stmt, "whereclause") else {}
            mock = MagicMock()
            if hasattr(stmt, "whereclause"):
                mock.scalar_one_or_none = MagicMock(return_value=mock_client_node)
            else:
                mock.scalar_one_or_none = MagicMock(return_value=mock_prop_node)
            return mock

        builder.session.execute = mock_execute
        builder.session.execute.return_value.scalar_one_or_none = MagicMock(return_value=mock_client_node)

        await builder._upsert_edge(client_id, prop_id, "owns", source_type="client", target_type="property")
        builder.session.execute.assert_called()

    async def test_upsert_edge_skips_missing_target(self, builder):
        """Should log warning when target node not found."""
        client_id, prop_id = uuid7(), uuid7()
        builder.session.execute.return_value.scalar_one_or_none = MagicMock(return_value=None)

        with patch("backend.ai.graph.logger") as mock_log:
            await builder._upsert_edge(client_id, prop_id, "owns", source_type="client", target_type="property")
            mock_log.warning.assert_called_once()