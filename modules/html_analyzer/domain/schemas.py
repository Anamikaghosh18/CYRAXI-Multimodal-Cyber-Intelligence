"""
Domain schemas for HTML / NLP Analyzer.
Conforms strictly to schemas/model-output.schema.json.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class FormSummary(BaseModel):
    action: str = ""
    method: str = "GET"
    has_password_input: bool = False
    is_action_external: bool = False


class DOMFeatures(BaseModel):
    title: str = ""
    meta_tags_count: int = 0
    form_action_count: int = 0
    forms: List[FormSummary] = Field(default_factory=list)
    external_links_ratio: float = 0.0
    empty_anchor_ratio: float = 0.0
    has_obfuscated_javascript: bool = False
    iframe_count: int = 0


class NLPSignals(BaseModel):
    urgency_cues: List[str] = Field(default_factory=list)
    credential_harvesting_intent_score: float = 0.0
    brand_mentions: List[str] = Field(default_factory=list)


class HTMLClassification(BaseModel):
    is_phishing_predicted: bool
    confidence_score: float = Field(ge=0.0, le=1.0)
    verdict: str = Field(pattern="^(phishing|not_phishing|suspicious)$")


class HTMLAnalysisResult(BaseModel):
    classification: HTMLClassification
    dom_features: DOMFeatures
    nlp_signals: NLPSignals


class AnalyzeHTMLRequest(BaseModel):
    observation_id: str
    run_id: str = "html_analysis_run"
    html_text: Optional[str] = None
    page_url: str = ""
