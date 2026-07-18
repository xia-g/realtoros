"""Tests for request context."""

import uuid

from backend.core.context import (
    RequestContext,
    get_request_context,
    reset_request_context,
    set_request_context,
)


class TestRequestContext:
    def test_create_defaults(self):
        ctx = RequestContext()
        assert ctx.request_id is not None
        assert len(ctx.request_id) == 16  # hex[:16]
        assert ctx.correlation_id is not None
        assert ctx.user_id is None
        assert ctx.tenant_id is None
        assert ctx.started_at is not None

    def test_create_explicit(self):
        ctx = RequestContext(
            request_id="req-123",
            correlation_id="corr-456",
            user_id="user-789",
            tenant_id="tenant-000",
        )
        assert ctx.request_id == "req-123"
        assert ctx.correlation_id == "corr-456"
        assert ctx.user_id == "user-789"
        assert ctx.tenant_id == "tenant-000"

    def test_to_dict(self):
        ctx = RequestContext(
            request_id="r1",
            correlation_id="c1",
            user_id="u1",
        )
        d = ctx.to_dict()
        assert d["request_id"] == "r1"
        assert d["correlation_id"] == "c1"
        assert d["user_id"] == "u1"
        assert "started_at" in d

    def test_context_var_roundtrip(self):
        ctx = RequestContext(request_id="roundtrip")
        set_request_context(ctx)
        retrieved = get_request_context()
        assert retrieved is not None
        assert retrieved.request_id == "roundtrip"
        reset_request_context()
        assert get_request_context() is None

    def test_context_var_outside_request(self):
        assert get_request_context() is None

    def test_reset_multiple_times(self):
        reset_request_context()
        reset_request_context()
        assert get_request_context() is None

    def test_inherit_uuid_format(self):
        ctx = RequestContext()
        # Should be hex-formatted UUID
        assert len(ctx.request_id) == 16
        assert len(ctx.correlation_id) == 16
