"""
Service layer for HTML / NLP Analyzer.
Orchestrates DOM parsing, NLP analysis, and envelope generation.
"""

import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from modules.html_analyzer.domain.interfaces import IHTMLFeatureExtractor, IHTMLClassifier
from modules.html_analyzer.domain.extractor import StandardHTMLFeatureExtractor
from modules.html_analyzer.models.classifier import HeuristicHTMLClassifier


class HTMLAnalysisService:
    """Core domain service for analyzing HTML documents."""

    def __init__(
        self,
        extractor: Optional[IHTMLFeatureExtractor] = None,
        classifier: Optional[IHTMLClassifier] = None,
    ):
        self._extractor = extractor or StandardHTMLFeatureExtractor()
        self._classifier = classifier or HeuristicHTMLClassifier()

    def analyze(
        self,
        observation_id: str,
        run_id: str,
        html_text: Optional[str],
        page_url: str = "",
    ) -> Dict[str, Any]:
        started = time.perf_counter()
        warnings: List[Dict[str, Any]] = []

        if not html_text:
            return {
                "schema_version": "1.0.0",
                "observation_id": observation_id,
                "run_id": run_id,
                "model": {
                    "name": "html_nlp_detector",
                    "version": "1.0.0",
                    "modality": "html_nlp",
                    "execution_hardware": "cpu",
                    "latency_ms": 0.0,
                },
                "status": "skipped",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "result": {},
                "warnings": [{
                    "code": "W_HTML_MISSING",
                    "message": "HTML artifact was not captured for observation",
                    "artifact_ref": "artifacts.html",
                }],
                "error_details": None,
            }

        extracted = self._extractor.extract(html_text, page_url=page_url)
        dom_features = extracted["dom_features"]
        nlp_signals = extracted["nlp_signals"]

        classification = self._classifier.classify(dom_features, nlp_signals)
        elapsed = round((time.perf_counter() - started) * 1000, 2)

        return {
            "schema_version": "1.0.0",
            "observation_id": observation_id,
            "run_id": run_id,
            "model": {
                "name": "html_nlp_detector",
                "version": "1.0.0",
                "modality": "html_nlp",
                "execution_hardware": "cpu",
                "latency_ms": elapsed,
            },
            "status": "success",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "result": {
                "classification": classification.model_dump(),
                "dom_features": dom_features,
                "nlp_signals": nlp_signals,
            },
            "warnings": warnings,
            "error_details": None,
        }
