"""
Computer Vision Logo Detector Module.
Preserves backwards-compatible functional interface and exposes service.
"""

from typing import Optional
from modules.cv_detector.service import CVDetectorService

_default_service = CVDetectorService()


def detect_logo_candidates(
    observation_id: str,
    run_id: str,
    coordinates_text: Optional[str] = None,
    screenshot_bytes: Optional[bytes] = None,
):
    """Public functional entry-point preserving 100% backward compatibility."""
    return _default_service.detect(
        observation_id=observation_id,
        run_id=run_id,
        coordinates_text=coordinates_text,
        screenshot_bytes=screenshot_bytes,
    )


__all__ = ["CVDetectorService", "detect_logo_candidates"]
