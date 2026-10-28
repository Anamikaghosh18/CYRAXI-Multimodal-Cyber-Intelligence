"""
OCR Analysis Domain Service.
Orchestrates image validation, OCR extraction, credential keyword detection, and envelope creation.
"""

import io
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from PIL import Image, ImageStat, UnidentifiedImageError

from modules.ocr_extractor.domain.interfaces import IOCREngine
from modules.ocr_extractor.models.tesseract_engine import TesseractOCREngine, make_warning

CREDENTIAL_KEYWORDS = [
    "password", "passwort", "login", "sign in",
    "username", "email", "e-mail", "verify account",
]


class OCRExtractorService:
    """Core domain service for OCR analysis."""

    def __init__(self, engine: Optional[IOCREngine] = None):
        self._engine = engine or TesseractOCREngine()

    def _usable_image(self, screenshot_bytes: bytes, warnings: List[Dict[str, Any]]) -> Optional[Image.Image]:
        try:
            with Image.open(io.BytesIO(screenshot_bytes)) as source:
                source.load()
                image = source.convert("RGB")
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
            warnings.append(make_warning(
                "W_OCR_INVALID_IMAGE",
                "Screenshot is corrupt or uses an unsupported image format",
                "artifacts.screenshot",
            ))
            return None

        if image.width < 20 or image.height < 20:
            warnings.append(make_warning(
                "W_OCR_IMAGE_TOO_SMALL",
                "Screenshot is too small for OCR",
                "artifacts.screenshot",
            ))
            return None

        if ImageStat.Stat(image.convert("L")).stddev[0] < 2:
            warnings.append(make_warning(
                "W_OCR_IMAGE_BLANK",
                "Screenshot appears blank or nearly uniform",
                "artifacts.screenshot",
            ))
            return None

        return image

    def extract(
        self,
        observation_id: str,
        run_id: str,
        ocr_text: Optional[str] = None,
        screenshot_bytes: Optional[bytes] = None,
    ) -> Dict[str, Any]:
        started = time.perf_counter()
        warnings: List[Dict[str, Any]] = []

        text = (ocr_text or "").strip()
        source = "precomputed_text" if text else "none"
        confidence_values: List[float] = []
        bounding_boxes: List[Dict[str, Any]] = []

        if screenshot_bytes:
            image = self._usable_image(screenshot_bytes, warnings)
            if image is not None:
                image_text, confidence_values, bounding_boxes = self._engine.extract_words(
                    image, warnings
                )
                if image_text:
                    text = image_text
                    source = "screenshot_ocr"
                else:
                    warnings.append(make_warning(
                        "W_OCR_NO_TEXT",
                        "OCR found no readable text in the screenshot",
                        "artifacts.screenshot",
                    ))
        elif not text:
            warnings.append(make_warning(
                "W_OCR_SCREENSHOT_MISSING",
                "Screenshot bytes were not supplied",
                "artifacts.screenshot",
            ))

        if source == "precomputed_text":
            warnings.append(make_warning(
                "W_OCR_PRECOMPUTED",
                "Used supplied OCR text; image OCR was unavailable or not supplied",
                "artifacts.ocr",
            ))

        if text:
            lower_text = text.lower()
            keywords = [
                keyword for keyword in CREDENTIAL_KEYWORDS
                if keyword in lower_text
            ]
            material_warnings = [
                w for w in warnings
                if w["code"] != "W_OCR_PRECOMPUTED"
            ]
            status = "partial" if material_warnings else "success"
        else:
            keywords = []
            status = "skipped"
            warnings.append(make_warning(
                "W_OCR_NO_USABLE_TEXT",
                "No usable OCR text was available",
                "artifacts.ocr",
            ))

        latency_ms = round((time.perf_counter() - started) * 1000, 2)

        return {
            "schema_version": "1.0.0",
            "observation_id": observation_id,
            "run_id": run_id,
            "model": {
                "name": "tesseract_ocr",
                "version": "1.0.0",
                "modality": "ocr",
                "execution_hardware": "cpu",
                "latency_ms": latency_ms,
            },
            "status": status,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "result": {
                "extracted_text_raw": text,
                "text_character_count": len(text),
                "confidence_mean": (
                    round(sum(confidence_values) / len(confidence_values), 4)
                    if confidence_values else None
                ),
                "bounding_boxes": bounding_boxes,
                "extracted_credentials_keywords": keywords,
                "identified_brands": [],
                "source": source,
            },
            "warnings": warnings,
            "error_details": None,
        }
