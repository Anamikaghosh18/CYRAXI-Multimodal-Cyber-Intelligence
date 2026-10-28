"""
OCR Extractor Module.
Preserves backwards-compatible functional interface and exposes service.
"""

from typing import Optional
import pytesseract
from modules.ocr_extractor.service import OCRExtractorService

_default_service = OCRExtractorService()


def extract_ocr(
    observation_id: str,
    run_id: str,
    ocr_text: Optional[str] = None,
    screenshot_bytes: Optional[bytes] = None,
):
    """Public functional entry-point preserving 100% backward compatibility."""
    return _default_service.extract(
        observation_id=observation_id,
        run_id=run_id,
        ocr_text=ocr_text,
        screenshot_bytes=screenshot_bytes,
    )


__all__ = ["OCRExtractorService", "extract_ocr", "pytesseract"]
