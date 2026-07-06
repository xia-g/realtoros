"""File security validation for document processing.

Validates before OCR:
- MIME type (magic bytes, not extension)
- File size limits
- Path traversal protection
"""

from __future__ import annotations

import mimetypes
import tempfile
from pathlib import Path
from typing import BinaryIO

from backend.core.logging import get_logger

logger = get_logger("knowledge")

ALLOWED_MIMES: set[str] = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/tiff",
}

MAX_FILE_SIZE_MB: int = 50
MAX_FILE_SIZE_BYTES: int = MAX_FILE_SIZE_MB * 1024 * 1024

SAFE_TEMP_DIR: Path = Path("/tmp/realtor_ocr")


class FileValidationError(Exception):
    """Raised when a file fails security validation."""


async def validate_file(path: str | Path) -> dict:
    """Validate a file before processing.

    Returns:
        dict with validated metadata: mime_type, size_bytes, safe_path

    Raises:
        FileValidationError if validation fails.
    """
    p = Path(path)

    # Path traversal check
    try:
        p = p.resolve(strict=True)
    except (FileNotFoundError, RuntimeError):
        raise FileValidationError(f"File not found or inaccessible: {path}")

    allowed_base = Path("/var/www/ttbot/storage").resolve() if Path("/var/www/ttbot/storage").exists() else Path.home().resolve()
    # If file is outside known safe directories, reject
    safe_dirs = [
        Path(tempfile.gettempdir()).resolve(),
        Path.home().resolve(),
        Path("/tmp").resolve(),
        Path("/var/www").resolve(),
    ]
    is_safe = any(str(p).startswith(str(d)) for d in safe_dirs)
    if not is_safe:
        raise FileValidationError(f"Path outside safe directories: {path}")

    # File size check
    try:
        size = p.stat().st_size
    except OSError:
        raise FileValidationError(f"Cannot read file size: {path}")

    if size > MAX_FILE_SIZE_BYTES:
        raise FileValidationError(
            f"File too large: {size / 1024 / 1024:.1f} MB "
            f"(max {MAX_FILE_SIZE_MB} MB)"
        )

    if size == 0:
        raise FileValidationError("File is empty")

    # MIME type validation via magic bytes
    try:
        import magic
        with open(p, "rb") as f:
            chunk = f.read(2048)
        mime = magic.from_buffer(chunk, mime=True)
    except ImportError:
        # Fallback: extension-based guess
        mime, _ = mimetypes.guess_type(str(p))
        logger.warning("python-magic not available, using extension-based MIME guess")

    if mime not in ALLOWED_MIMES:
        raise FileValidationError(
            f"Unsupported file type: {mime or 'unknown'} "
            f"(allowed: {', '.join(sorted(ALLOWED_MIMES))})"
        )

    return {
        "mime_type": mime,
        "size_bytes": size,
        "path": str(p),
        "safe": True,
    }


def setup_safe_temp() -> Path:
    """Create and return a safe temporary directory for OCR processing."""
    SAFE_TEMP_DIR.mkdir(parents=True, exist_ok=True)
    return SAFE_TEMP_DIR