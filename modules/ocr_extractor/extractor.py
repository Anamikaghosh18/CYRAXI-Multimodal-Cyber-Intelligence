import io
import math
import os
import time
from datetime import datetime, timezone

import pytesseract
from PIL import Image, ImageStat, UnidentifiedImageError
from pytesseract import Output


TESSERACT_PATH = os.environ.get(
    "CYRAXI_TESSERACT_CMD",
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
)

if os.path.isfile(TESSERACT_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH


CREDENTIAL_KEYWORDS = [
    "password", "passwort", "login", "sign in",
    "username", "email", "e-mail", "verify account",
]


def _warning(code, message, artifact_ref):
    return {
        "code": code,
        "message": message,
        "artifact_ref": artifact_ref,
    }


def _base_output(observation_id, run_id, started):
    return {
        "schema_version": "1.0.0",
        "observation_id": observation_id,
        "run_id": run_id,
        "model": {
            "name": "tesseract_ocr",
            "version": "1.0.0",
            "modality": "ocr",
            "execution_hardware": "cpu",
            "latency_ms": round(
                (time.perf_counter() - started) * 1000, 2
            ),
        },
        "status": "success",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "result": {},
        "warnings": [],
        "error_details": None,
    }


def _usable_image(screenshot_bytes, warnings):
    """Decode an image and reject tiny or nearly uniform screenshots."""
    try:
        with Image.open(io.BytesIO(screenshot_bytes)) as source:
            source.load()
            image = source.convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        warnings.append(_warning(
            "W_OCR_INVALID_IMAGE",
            "Screenshot is corrupt or uses an unsupported image format",
            "artifacts.screenshot",
        ))
        return None

    if image.width < 20 or image.height < 20:
        warnings.append(_warning(
            "W_OCR_IMAGE_TOO_SMALL",
            "Screenshot is too small for OCR",
            "artifacts.screenshot",
        ))
        return None

    if ImageStat.Stat(image.convert("L")).stddev[0] < 2:
        warnings.append(_warning(
            "W_OCR_IMAGE_BLANK",
            "Screenshot appears blank or nearly uniform",
            "artifacts.screenshot",
        ))
        return None

    return image


def _run_tesseract(image, warnings):
    """Return image OCR text, normalized confidence, and contract boxes."""
    try:
        data = pytesseract.image_to_data(
            image,
            output_type=Output.DICT,
            config="--psm 3",
        )
    except pytesseract.TesseractNotFoundError:
        warnings.append(_warning(
            "W_OCR_ENGINE_MISSING",
            "Tesseract executable was not found; precomputed OCR may be used",
            "artifacts.screenshot",
        ))
        return "", [], []
    except pytesseract.TesseractError:
        warnings.append(_warning(
            "W_OCR_ENGINE_ERROR",
            "Tesseract could not process the screenshot; precomputed OCR may be used",
            "artifacts.screenshot",
        ))
        return "", [], []
    except OSError:
        warnings.append(_warning(
            "W_OCR_ENGINE_MISSING",
            "Tesseract executable could not be started; precomputed OCR may be used",
            "artifacts.screenshot",
        ))
        return "", [], []

    words = []
    confidences = []
    boxes = []
    for index, raw_word in enumerate(data.get("text", [])):
        word = str(raw_word).strip()
        if not word:
            continue

        try:
            left = int(data["left"][index])
            top = int(data["top"][index])
            width = int(data["width"][index])
            height = int(data["height"][index])
            raw_confidence = float(data["conf"][index])
        except (KeyError, IndexError, TypeError, ValueError, OverflowError):
            continue

        if (
            width <= 0
            or height <= 0
            or left < 0
            or top < 0
            or left + width > image.width
            or top + height > image.height
        ):
            continue

        confidence = None
        if math.isfinite(raw_confidence) and raw_confidence >= 0:
            confidence = round(min(1.0, raw_confidence / 100.0), 4)
            confidences.append(confidence)

        words.append(word)
        boxes.append({
            "text": word,
            "box_2d": [left, top, left + width, top + height],
            "confidence": confidence,
        })

    return " ".join(words).strip(), confidences, boxes


def extract_ocr(
    observation_id,
    run_id,
    ocr_text=None,
    screenshot_bytes=None,
):
    """Extract screenshot text when possible, falling back to supplied OCR."""
    started = time.perf_counter()
    output = _base_output(observation_id, run_id, started)
    warnings = []

    text = (ocr_text or "").strip()
    source = "precomputed_text" if text else "none"
    confidence_values = []
    bounding_boxes = []

    if screenshot_bytes:
        image = _usable_image(screenshot_bytes, warnings)
        if image is not None:
            image_text, confidence_values, bounding_boxes = _run_tesseract(
                image, warnings
            )
            if image_text:
                text = image_text
                source = "screenshot_ocr"
            else:
                warnings.append(_warning(
                    "W_OCR_NO_TEXT",
                    "OCR found no readable text in the screenshot",
                    "artifacts.screenshot",
                ))
    elif not text:
        warnings.append(_warning(
            "W_OCR_SCREENSHOT_MISSING",
            "Screenshot bytes were not supplied",
            "artifacts.screenshot",
        ))

    if source == "precomputed_text":
        warnings.append(_warning(
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
            warning for warning in warnings
            if warning["code"] != "W_OCR_PRECOMPUTED"
        ]
        output["status"] = "partial" if material_warnings else "success"
    else:
        keywords = []
        output["status"] = "skipped"
        warnings.append(_warning(
            "W_OCR_NO_USABLE_TEXT",
            "No usable OCR text was available",
            "artifacts.ocr",
        ))

    output["result"] = {
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
    }
    output["warnings"] = warnings
    output["model"]["latency_ms"] = round(
        (time.perf_counter() - started) * 1000, 2
    )
    return output
