"""Application exception hierarchy.

All domain-level errors inherit from AppError.
Every exception is serializable and structured-logging compatible.
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base application error — structured, serializable, logged automatically."""

    def __init__(
        self,
        message: str = "Application error",
        code: str = "APP_ERROR",
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": self.code,
            "message": self.message,
            "details": self.details,
        }


class ValidationError(AppError):
    def __init__(
        self,
        message: str = "Validation failed",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message=message, code="VALIDATION_ERROR", status_code=400, details=details)


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(message=message, code="NOT_FOUND", status_code=404)


class ConflictError(AppError):
    def __init__(self, message: str = "Resource conflict") -> None:
        super().__init__(message=message, code="CONFLICT", status_code=409)


class ForbiddenError(AppError):
    def __init__(self, message: str = "Access denied") -> None:
        super().__init__(message=message, code="FORBIDDEN", status_code=403)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(message=message, code="UNAUTHORIZED", status_code=401)


class LeadStateError(AppError):
    def __init__(self, message: str = "Invalid lead state transition") -> None:
        super().__init__(message=message, code="LEAD_STATE_ERROR", status_code=422)


class DuplicateEntityError(AppError):
    def __init__(self, message: str = "Entity already exists") -> None:
        super().__init__(message=message, code="DUPLICATE_ENTITY", status_code=409)