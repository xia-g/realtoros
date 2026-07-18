"""OCR Runtime — text extraction from PDFs and images.

Supported formats: PDF, JPG, PNG, TIFF
Primary engine: PaddleOCR PP-OCRv4
Fallback: Tesseract 5
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from backend.core.logging import get_logger

logger = get_logger("knowledge")


class OCRProvider(Enum):
    PADDLE = "paddle"
    TESSERACT = "tesseract"


@dataclass
class OCRResult:
    text: str
    confidence: float
    page_count: int = 1
    provider: str = "paddle"
    metadata: dict = field(default_factory=dict)


class OCRService:
    """Extract text from documents using PaddleOCR with Tesseract fallback."""

    def __init__(self):
        self._paddle = None
        self._tesseract_available = False
        self._check_tesseract()

    def _check_tesseract(self) -> None:
        import shutil
        self._tesseract_available = shutil.which("tesseract") is not None

    def _get_paddle(self):
        if self._paddle is None:
            try:
                from paddleocr import PaddleOCR
                self._paddle = PaddleOCR(use_angle_cls=True, lang="ru", show_log=False)
            except ImportError:
                logger.warning("PaddleOCR not available, will use Tesseract fallback")
        return self._paddle

    async def extract(self, file_path: str | Path, mime_type: str | None = None) -> OCRResult:
        from backend.ai.ocr.file_security import validate_file, FileValidationError
        from backend.core.logging import get_logger

        try:
            info = await validate_file(file_path)
        except FileValidationError as e:
            logger.error("file_validation_failed", path=str(file_path), error=str(e))
            raise

        path = Path(info["path"])

        try:
            if info["mime_type"] == "application/pdf":
                result = await asyncio.wait_for(
                    self._process_pdf(path), timeout=300
                )
            else:
                result = await asyncio.wait_for(
                    self._process_image(path), timeout=120
                )
            return result
        except asyncio.TimeoutError:
            logger.error("ocr_timeout", path=str(file_path), mime=info["mime_type"])
            raise TimeoutError(f"OCR processing timed out for {file_path}")
        except Exception as e:
            logger.exception("ocr_failed", path=str(file_path), error=str(e))
            raise

    async def _process_pdf(self, path: Path) -> OCRResult:
        from backend.ai.ocr.file_security import setup_safe_temp
        import fitz  # PyMuPDF
        doc = fitz.open(path)
        full_text = []
        total_conf = 0.0
        pages = len(doc)

        safe_dir = setup_safe_temp()

        for page_num, page in enumerate(doc, 1):
            pix = page.get_pixmap(dpi=300)
            img_path = safe_dir / f"ocr_page_{path.stem}_{page_num}.png"
            pix.save(str(img_path))
            result = await self._process_image(Path(img_path), provider=OCRProvider.PADDLE)
            full_text.append(f"--- Page {page_num} ---\n{result.text}")
            total_conf += result.confidence
            # Clean up temp image
            img_path.unlink(missing_ok=True)

        doc.close()
        avg_conf = total_conf / max(pages, 1)
        logger.info("ocr_completed", file=str(path), pages=pages, confidence=round(avg_conf, 3))
        return OCRResult(
            text="\n".join(full_text),
            confidence=avg_conf,
            page_count=pages,
            provider="paddle",
        )

    async def _process_image(self, path: Path, provider: OCRProvider | None = None) -> OCRResult:
        paddle = self._get_paddle()
        if paddle and provider != OCRProvider.TESSERACT:
            try:
                result = paddle.ocr(str(path), cls=True)
                text = []
                confs = []
                for line_group in result:
                    if line_group is None:
                        continue
                    for line in line_group:
                        if isinstance(line, list) and len(line) >= 2:
                            text.append(line[1][0])
                            confs.append(line[1][1])
                if text:
                    avg_conf = sum(confs) / len(confs)
                    return OCRResult(text="\n".join(text), confidence=avg_conf, provider="paddle")
            except Exception as e:
                logger.warning("PaddleOCR failed, falling back to Tesseract", error=str(e))

        # Tesseract fallback
        if self._tesseract_available:
            import subprocess
            result = subprocess.run(
                ["tesseract", str(path), "stdout", "-l", "rus+eng"],
                capture_output=True, text=True, timeout=60,
            )
            text = result.stdout.strip()
            if text:
                return OCRResult(text=text, confidence=0.85, provider="tesseract")

        return OCRResult(text="", confidence=0.0, provider="none")