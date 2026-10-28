"""
Domain schemas for Computer Vision Logo Detector.
Conforms strictly to schemas/model-output.schema.json.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class CropMetadata(BaseModel):
    width: int
    height: int
    aspect_ratio: float


class DetectedElement(BaseModel):
    element_type: str = "logo"
    candidate_id: str
    detection_source: str = "precomputed_coordinates"
    box_2d: List[int] = Field(description="[left, top, right, bottom]")
    crop: CropMetadata
    detector_confidence: Optional[float] = None
    brand_matches: List[Dict[str, Any]] = Field(default_factory=list)
    brand_identified: bool = False


class VisualIdentityVerdict(BaseModel):
    top_matched_brand: Optional[str] = None
    top_similarity_score: Optional[float] = None
    confidence: Optional[float] = None


class CVClassification(BaseModel):
    has_detected_logo: bool
    num_candidates_found: int


class CVResultData(BaseModel):
    classification: CVClassification
    detected_elements: List[DetectedElement] = Field(default_factory=list)
    visual_identity_verdict: VisualIdentityVerdict
    brand_match_performed: bool = False


class DetectCVRequest(BaseModel):
    observation_id: str
    run_id: str = "cv_detection_run"
    coordinates_text: Optional[str] = None
    screenshot_base64: Optional[str] = None
