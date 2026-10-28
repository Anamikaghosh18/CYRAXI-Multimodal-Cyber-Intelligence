"""
Tesseract OCR Engine wrapper.
Implements IOCREngine with PyTesseract fallback handling.
"""

import os
from typing import Tuple, List, Dict, Any
from PIL import Image
import pytesseract
from pytesseract import Output

from modules.ocr_extractor.domain.interfaces import IOCREngine

TESSERACT_PATH = os.environ.get(
    "CYRAXI_TESSERACT_CMD",
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
)

if os.path.isfile(TESSERACT_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH


def make_warning(code: str, message: str, artifact_ref: str) -> Dict[str, str]:
    return {"code": code, "message": message, "artifact_ref": artifact_ref}


class TesseractOCREngine(IOCREngine):
    """Engine backed by Tesseract CLI via pytesseract."""

    def extract_words(
        self,
        image: Image.Image,
        warnings: List[Dict[str, Any]]
    ) -> Tuple[str, List[float], List[Dict[str, Any]]]:
        try:
            data = pytesseract.image_to_data(
                image,
                output_type=Output.DICT,
                config="--psm 3",
            )
        except pytesseract.TesseractNotFoundError:
            warnings.append(make_warning(
                "W_OCR_ENGINE_MISSING",
                "Tesseract executable is not installed or not in PATH",
                "artifacts.ocr",
            ))
            return "", [], []
        except (pytesseract.TesseractError, OSError, ValueError):
            warnings.append(make_warning(
                "W_OCR_EXECUTION_FAILED",
                "Tesseract failed during screenshot text extraction",
                "artifacts.screenshot",
            ))
            return "", [], []

        raw_words = data.get("text", [])
        raw_confs = data.get("conf", [])
        lefts = data.get("left", [])
        tops = data.get("top", [])
        widths = data.get("width", [])
        heights = data.get("height", [])

        words = []
        confidences = []
        boxes = []

        for index, raw_word in enumerate(raw_words):
            word = str(raw_word).strip()
            if not word:
                continue

            try:
                raw_conf = float(raw_confs[index])
            except (IndexError, TypeError, ValueError):
                raw_conf = -1.0

            try:
                left = int(lefts[index])
                top = int(tops[index])
                width = int(widths[index])
                height = int(heights[index])
            except (IndexError, TypeError, ValueError):
                left, top, width, height = 0, 0, 0, 0

            confidence = round(raw_conf / 100.0, 4) if raw_conf >= 0 else None
            if confidence is not None:
                confidences.append(confidence)

            words.append(word)
            boxes.append({
                "text": word,
                "box_2d": [left, top, left + width, top + height],
                "confidence": confidence,
            })

        return " ".join(words).strip(), confidences, boxes
