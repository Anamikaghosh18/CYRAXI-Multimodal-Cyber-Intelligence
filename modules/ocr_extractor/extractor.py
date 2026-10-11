import time
from datetime import datetime, timezone


CREDENTIAL_KEYWORDS = [
    "password", "passwort", "login", "sign in",
    "username", "email", "e-mail", "verify account",
]


def extract_ocr(observation_id, run_id, ocr_text=None):
    started = time.perf_counter()

    if not ocr_text or not ocr_text.strip():
        return {
            "schema_version": "1.0.0",
            "observation_id": observation_id,
            "run_id": run_id,
            "model": {
                "name": "ocr_text_extractor",
                "version": "1.0.0",
                "modality": "ocr",
                "execution_hardware": "cpu",
                "latency_ms": 0.0,
            },
            "status": "skipped",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "result": {},
            "warnings": [{
                "code": "W_OCR_MISSING",
                "message": "No precomputed OCR text was available",
                "artifact_ref": "artifacts.ocr",
            }],
            "error_details": None,
        }

    text = ocr_text.strip()
    lower_text = text.lower()
    keywords = [
        keyword for keyword in CREDENTIAL_KEYWORDS
        if keyword in lower_text
    ]

    return {
        "schema_version": "1.0.0",
        "observation_id": observation_id,
        "run_id": run_id,
        "model": {
            "name": "ocr_text_extractor",
            "version": "1.0.0",
            "modality": "ocr",
            "execution_hardware": "cpu",
            "latency_ms": round(
                (time.perf_counter() - started) * 1000, 2
            ),
        },
        "status": "success",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "result": {
            "extracted_text_raw": text,
            "text_character_count": len(text),
            "confidence_mean": None,
            "bounding_boxes": [],
            "extracted_credentials_keywords": keywords,
            "identified_brands": [],
        },
        "warnings": [{
            "code": "W_OCR_PRECOMPUTED",
            "message": "Used supplied OCR text; no image OCR was performed",
            "artifact_ref": "artifacts.ocr",
        }],
        "error_details": None,
    }
