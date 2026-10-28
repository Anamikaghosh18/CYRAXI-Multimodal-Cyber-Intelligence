"""
Domain schemas for OCR Extractor.
Conforms strictly to schemas/model-output.schema.json.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    text: str
    box_2d: List[int] = Field(description="[left, top, right, bottom]")
    confidence: Optional[float] = None


class OCRResultData(BaseModel):
    extracted_text_raw: str = ""
    text_character_count: int = 0
    confidence_mean: Optional[float] = None
    bounding_boxes: List[BoundingBox] = Field(default_factory=list)
    extracted_credentials_keywords: List[str] = Field(default_factory=list)
    identified_brands: List[str] = Field(default_factory=list)
    source: str = "none"


class ExtractOCRRequest(BaseModel):
    observation_id: str
    run_id: str = "ocr_extraction_run"
    ocr_text: Optional[str] = None
    screenshot_base64: Optional[str] = None
