import io
import math
import re
import time
from datetime import datetime, timezone

from PIL import Image, UnidentifiedImageError


def _warning(code, message, artifact_ref):
    return {
        "code": code,
        "message": message,
        "artifact_ref": artifact_ref,
    }


def _envelope(observation_id, run_id, started, status, result, warnings):
    return {
        "schema_version": "1.0.0",
        "observation_id": observation_id,
        "run_id": run_id,
        "model": {
            "name": "cv_logo_detector",
            "version": "1.2.0",
            "modality": "computer_vision",
            "execution_hardware": "cpu",
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        },
        "status": status,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "result": result,
        "warnings": warnings,
        "error_details": None,
    }


def _parse_pixel_xyxy(line):
    """Parse pixel xyxy coordinates in fixture or observed archive syntax.

    Archive rows use ``(x1, y1, x2, y2)\tconfidence``. The source confidence
    is validated but deliberately not returned or represented as this
    pipeline's detector confidence.
    """
    number = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
    archive_row = re.fullmatch(
        rf"\(\s*({number})\s*,\s*({number})\s*,\s*({number})\s*,\s*({number})\s*\)\s+({number})",
        line.strip(),
    )
    if archive_row:
        values = [float(value) for value in archive_row.groups()[:4]]
        source_confidence = float(archive_row.group(5))
        if not math.isfinite(source_confidence) or not 0 <= source_confidence <= 1:
            raise ValueError("Source coordinate confidence must be in [0, 1]")
    else:
        values = [float(value) for value in line.split()]
        if len(values) != 4:
            raise ValueError("Expected four pixel coordinates or archive tuple plus source confidence")
    if not all(math.isfinite(value) for value in values):
        raise ValueError("Coordinates must be finite numbers")
    return values


def detect_logo_candidates(
    observation_id,
    run_id,
    coordinates_text=None,
    screenshot_bytes=None,
):
    """Crop coordinate-provided logo candidates without claiming brand matches."""
    started = time.perf_counter()

    if not isinstance(coordinates_text, str) or not coordinates_text.strip():
        return _envelope(
            observation_id,
            run_id,
            started,
            "skipped",
            {},
            [_warning(
                "W_CV_COORDINATES_MISSING",
                "No precomputed logo coordinates were supplied",
                "artifacts.auxiliary.yolo_coords_path",
            )],
        )

    if not screenshot_bytes:
        return _envelope(
            observation_id,
            run_id,
            started,
            "skipped",
            {},
            [_warning(
                "W_CV_SCREENSHOT_MISSING",
                "Screenshot bytes are required to validate and crop candidates",
                "artifacts.screenshot",
            )],
        )

    try:
        with Image.open(io.BytesIO(screenshot_bytes)) as source:
            source.load()
            image = source.convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        return _envelope(
            observation_id,
            run_id,
            started,
            "error",
            {},
            [_warning(
                "W_CV_INVALID_SCREENSHOT",
                "Screenshot is corrupt or uses an unsupported image format",
                "artifacts.screenshot",
            )],
        )

    image_width, image_height = image.size
    candidates = []
    warnings = []
    rejected_count = 0

    for line_number, line in enumerate(coordinates_text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            x1, y1, x2, y2 = _parse_pixel_xyxy(line)
            if not (0 <= x1 < x2 <= image_width):
                raise ValueError("Horizontal coordinates are out of bounds")
            if not (0 <= y1 < y2 <= image_height):
                raise ValueError("Vertical coordinates are out of bounds")

            # Floor the top-left and ceil the bottom-right so fractional pixel
            # bounds include their full region. Validation above keeps the
            # resulting crop within the screenshot.
            left = max(0, math.floor(x1))
            top = max(0, math.floor(y1))
            right = min(image_width, math.ceil(x2))
            bottom = min(image_height, math.ceil(y2))
            if right <= left or bottom <= top:
                raise ValueError("Coordinate box produces an empty crop")

            crop = image.crop((left, top, right, bottom))
            if crop.width <= 0 or crop.height <= 0:
                raise ValueError("Coordinate box produces an empty crop")

            candidates.append({
                "element_type": "logo",
                "candidate_id": f"candidate_{len(candidates) + 1}",
                "detection_source": "precomputed_coordinates",
                "box_2d": [left, top, right, bottom],
                "crop": {
                    "width": crop.width,
                    "height": crop.height,
                    "aspect_ratio": round(crop.width / crop.height, 4),
                },
                "detector_confidence": None,
                "brand_matches": [],
                "brand_identified": False,
            })
        except (ValueError, OverflowError):
            rejected_count += 1
            warnings.append(_warning(
                "W_CV_INVALID_COORDINATE_LINE",
                f"Rejected invalid coordinate line {line_number}",
                "artifacts.auxiliary.yolo_coords_path",
            ))

    if not candidates:
        if not warnings:
            warnings.append(_warning(
                "W_CV_NO_CANDIDATES",
                "No candidate coordinates were present",
                "artifacts.auxiliary.yolo_coords_path",
            ))
        result = {
            "classification": {
                "has_detected_logo": False,
                "num_candidates_found": 0,
            },
            "detected_elements": [],
            "visual_identity_verdict": {
                "top_matched_brand": None,
                "top_similarity_score": None,
                "confidence": None,
            },
            "brand_match_performed": False,
        }
        status = "partial" if rejected_count else "skipped"
    else:
        warnings.append(_warning(
            "W_CV_BRAND_MATCH_UNAVAILABLE",
            "Candidate crops are available, but no verified detector weights or reference brand gallery are present; candidates are not brand identifications",
            "data/reference_brands",
        ))
        result = {
            "classification": {
                "has_detected_logo": True,
                "num_candidates_found": len(candidates),
            },
            "detected_elements": candidates,
            "visual_identity_verdict": {
                "top_matched_brand": None,
                "top_similarity_score": None,
                "confidence": None,
            },
            "brand_match_performed": False,
        }
        status = "partial"

    return _envelope(
        observation_id,
        run_id,
        started,
        status,
        result,
        warnings,
    )
