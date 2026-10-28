"""
Computer Vision Detector package exports.
"""

from modules.cv_detector.detector import detect_logo_candidates
from modules.cv_detector.service import CVDetectorService

__all__ = ["detect_logo_candidates", "CVDetectorService"]
