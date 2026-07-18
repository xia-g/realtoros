"""Tests for exception system."""

import pytest

from backend.core.exceptions import (
    AppError,
    ConflictError,
    DuplicateEntityError,
    ForbiddenError,
    LeadStateError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)


class TestAppError:
    def test_base_fields(self):
        err = AppError(code="TEST_ERR", message="Something went wrong")
        assert err.code == "TEST_ERR"
        assert err.message == "Something went wrong"
        assert err.details == {}
        assert err.metadata == {}

    def test_with_details_and_metadata(self):
        err = AppError(
            code="TEST_ERR",
            message="test",
            details={"field": "name"},
            metadata={"trace_id": "abc"},
        )
        assert err.details == {"field": "name"}
        assert err.metadata == {"trace_id": "abc"}

    def test_to_dict(self):
        err = AppError(code="ERR", message="msg", details={"key": "val"})
        d = err.to_dict()
        assert d == {"code": "ERR", "message": "msg", "details": {"key": "val"}}

    def test_serializable(self):
        import json
        err = AppError(code="SER", message="serializable")
        json.dumps(err.to_dict())

    def test_repr(self):
        err = AppError(code="REPR", message="repr test")
        r = repr(err)
        assert "AppError" in r
        assert "REPR" in r


class TestDerivedErrors:
    def test_validation_error(self):
        err = ValidationError(details={"field": "email"})
        assert err.code == "VALIDATION_ERROR"
        assert isinstance(err, AppError)

    def test_not_found_error(self):
        err = NotFoundError(message="User not found")
        assert err.code == "NOT_FOUND"
        assert err.message == "User not found"

    def test_conflict_error(self):
        err = ConflictError()
        assert err.code == "CONFLICT"
        assert err.message == "Resource conflict"

    def test_forbidden_error(self):
        err = ForbiddenError()
        assert err.code == "FORBIDDEN"

    def test_unauthorized_error(self):
        err = UnauthorizedError()
        assert err.code == "UNAUTHORIZED"

    def test_lead_state_error(self):
        err = LeadStateError(
            message="Cannot convert lead in 'new' state",
            details={"current": "new", "target": "converted"},
        )
        assert err.code == "LEAD_STATE_ERROR"
        assert err.details["current"] == "new"

    def test_duplicate_entity_error(self):
        err = DuplicateEntityError(details={"email": "dupe@example.com"})
        assert err.code == "DUPLICATE_ENTITY"
        assert isinstance(err, ConflictError) is False  # sibling, not child
        assert isinstance(err, AppError)

    def test_default_messages(self):
        assert ValidationError().message == "Validation failed"
        assert NotFoundError().message == "Resource not found"
        assert ConflictError().message == "Resource conflict"
        assert ForbiddenError().message == "Access forbidden"
        assert UnauthorizedError().message == "Authentication required"
        assert LeadStateError().message == "Invalid lead state transition"
        assert DuplicateEntityError().message == "Duplicate entity"

    def test_exception_hierarchy(self):
        """All domain errors are also AppError."""
        errors = [
            ValidationError(),
            NotFoundError(),
            ConflictError(),
            ForbiddenError(),
            UnauthorizedError(),
            LeadStateError(),
            DuplicateEntityError(),
        ]
        for err in errors:
            assert isinstance(err, AppError), f"{type(err).__name__} is not an AppError"
            assert isinstance(err, Exception)
