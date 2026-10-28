"""
Computer Vision Logo Detector Domain Service.
Orchestrates screenshot decoding, coordinate parsing, bounding verification, and crop extraction.
"""

import io
import math
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from PIL import Image, UnidentifiedImageError

from modules.cv_detector.domain.interfaces import ICoordinateParser
from modules.cv_detector.domain.parser import StandardCoordinateParser


def make_warning(code: str, message: str, artifact_ref: str) -> Dict[str, str]:
    return {"code": code, "message": message, "artifact_ref": artifact_ref}


def make_envelope(observation_id: str, run_id: str, started: float, status: str, result: Dict[str, Any], warnings: List[Dict[str, Any]]) -> Dict[str, Any]:
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


class CVDetectorService:
    """Core domain service for logo detection and cropping."""

    def __init__(self, parser: Optional[ICoordinateParser] = None):
        self._parser = parser or StandardCoordinateParser()

    def detect(
        self,
        observation_id: str,
        run_id: str,
        coordinates_text: Optional[str] = None,
        screenshot_bytes: Optional[bytes] = None,
    ) -> Dict[str, Any]:
        started = time.perf_counter()

        if not isinstance(coordinates_text, str) or not coordinates_text.strip():
            return make_envelope(
                observation_id,
                run_id,
                started,
                "skipped",
                {},
                [make_warning(
                    "W_CV_COORDINATES_MISSING",
                    "No precomputed logo coordinates were supplied",
                    "artifacts.auxiliary.yolo_coords_path",
                )],
            )

        if not screenshot_bytes:
            return make_envelope(
                observation_id,
                run_id,
                started,
                "skipped",
                {},
                [make_warning(
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
            return make_envelope(
                observation_id,
                run_id,
                started,
                "error",
                {},
                [make_warning(
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
                x1, y1, x2, y2 = self._parser.parse_coordinates(line)
                if not (0 <= x1 < x2 <= image_width):
                    raise ValueError("Horizontal coordinates are out of bounds")
                if not (0 <= y1 < y2 <= image_height):
                    raise ValueError("Vertical coordinates are out of bounds")

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
                warnings.append(make_warning(
                    "W_CV_INVALID_COORDINATE_LINE",
                    f"Rejected invalid coordinate line {line_number}",
                    "artifacts.auxiliary.yolo_coords_path",
                ))

        if not candidates:
            if not warnings:
                warnings.append(make_warning(
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
            warnings.append(make_warning(
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

        return make_envelope(
            observation_id,
            run_id,
            started,
            status,
            result,
            warnings,
        )
