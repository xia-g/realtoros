"""Tests for file security validation."""

import tempfile
from pathlib import Path

import pytest


class TestFileValidation:
    async def test_rejects_empty_file(self):
        from backend.ai.ocr.file_security import validate_file, FileValidationError
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"")
            path = f.name

        with pytest.raises(FileValidationError, match="empty"):
            await validate_file(path)

    async def test_rejects_text_file(self):
        from backend.ai.ocr.file_security import validate_file, FileValidationError
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"hello world")
            path = f.name

        with pytest.raises(FileValidationError, match="Unsupported"):
            await validate_file(path)

    async def test_rejects_path_traversal(self):
        from backend.ai.ocr.file_security import validate_file, FileValidationError
        with pytest.raises((FileValidationError, FileNotFoundError)):
            await validate_file("/etc/passwd")