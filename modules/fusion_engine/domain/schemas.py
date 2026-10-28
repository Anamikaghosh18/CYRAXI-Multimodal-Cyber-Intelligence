"""
Domain schemas for Multimodal Fusion Engine.
Conforms strictly to schemas/model-output.schema.json.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ModalityEvidenceSummary(BaseModel):
    modality: str
    observed_signal: str
    score: Optional[float] = None
    limitations: List[str] = Field(default_factory=list)


class FusionClassification(BaseModel):
    is_phishing_predicted: Optional[bool] = None
    confidence_score: Optional[float] = None
    verdict: Optional[str] = None


class FusionResultData(BaseModel):
    classification: FusionClassification
    fused_probability: Optional[float] = None
    contributing_modalities: List[str] = Field(default_factory=list)
    calibrated_modalities: List[str] = Field(default_factory=list)
    evidence_modalities: List[str] = Field(default_factory=list)
    active_weights: Dict[str, float] = Field(default_factory=dict)
    evidence_summary: List[ModalityEvidenceSummary] = Field(default_factory=list)


class FuseOutputsRequest(BaseModel):
    observation_id: str
    run_id: str = "fusion_engine_run"
    outputs: List[Dict[str, Any]]
