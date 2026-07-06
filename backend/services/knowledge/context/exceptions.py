"""Context Builder — domain exceptions."""

from backend.core.exceptions import AppError


class ContextOverflowError(AppError):
    """Raised when context exceeds hard cap after all truncation steps."""
    code = "CONTEXT_OVERFLOW"
    status_code = 400

    def __init__(self, total_tokens: int, hard_cap: int = 6800):
        super().__init__(
            code=self.code,
            message=f"Context too large: {total_tokens} > {hard_cap}",
            details={"total_tokens": total_tokens, "hard_cap": hard_cap},
        )


class ContextBuildError(AppError):
    """Raised when context cannot be built for unexpected reasons."""
    code = "CONTEXT_BUILD_ERROR"
    status_code = 500

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(
            code=self.code,
            message=message,
            details=details or {},
        )