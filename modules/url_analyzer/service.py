"""
URL Analysis Pipeline Service
Orchestrates extraction, model inference, validation, and envelope wrapping.
Follows Single Responsibility Principle (SRP) and Open-Closed Principle (OCP).
"""

import time
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from urllib.parse import urlparse

from modules.url_analyzer.domain.interfaces import IURLFeatureExtractor, IURLClassifier
from modules.url_analyzer.domain.schemas import (
    URLFeatureSet,
    URLModelOutputEnvelope,
    URLAnalysisResult,
    ExtractedURLIndicators,
    ModelMetadata,
    WarningItem,
)
from modules.url_analyzer.domain.extractor import StandardURLFeatureExtractor
from modules.url_analyzer.models.heuristic_baseline import HeuristicURLClassifier


def generate_observation_id(url: str, custom_id: Optional[str] = None) -> str:
    """Generate deterministic canonical observation ID if none provided."""
    if custom_id and custom_id.startswith("obs_") and len(custom_id) == 36:
        return custom_id
    seed = f"adhoc_url:{url}".encode("utf-8")
    return f"obs_{hashlib.md5(seed).hexdigest()}"


class URLAnalysisService:
    """Core domain service for analyzing URLs and returning standardized envelopes."""

    def __init__(
        self,
        classifier: Optional[IURLClassifier] = None,
        extractor: Optional[IURLFeatureExtractor] = None,
        hardware: str = "cpu"
    ):
        self._extractor = extractor or StandardURLFeatureExtractor()
        self._classifier = classifier or HeuristicURLClassifier()
        self._hardware = hardware

    @property
    def classifier(self) -> IURLClassifier:
        return self._classifier

    def analyze(
        self,
        raw_url: str,
        observation_id: Optional[str] = None,
        run_id: str = "url_pipeline_run"
    ) -> URLModelOutputEnvelope:
        """Analyze a URL and wrap the result in the canonical ModelOutputEnvelope."""
        obs_id = generate_observation_id(raw_url, observation_id)
        warnings = []

        # Validate URL presence
        if not raw_url or not raw_url.strip():
            return URLModelOutputEnvelope(
                schema_version="1.0.0",
                observation_id=obs_id,
                run_id=run_id,
                model=ModelMetadata(
                    name=self._classifier.model_name,
                    version=self._classifier.version,
                    modality="url",
                    execution_hardware=self._hardware,
                    latency_ms=0.0
                ),
                status="skipped",
                created_at=datetime.now(timezone.utc).isoformat(),
                result={},
                warnings=[
                    WarningItem(
                        code="W_URL_EMPTY",
                        message="URL string is empty or whitespace",
                        artifact_ref="url.raw"
                    )
                ]
            )

        t0 = time.perf_counter()
        try:
            # 1. Feature Extraction
            features = self._extractor.extract(raw_url)

            # 2. Model Prediction
            classification = self._classifier.predict_features(features)

            latency_ms = round((time.perf_counter() - t0) * 1000, 2)

            # 3. Extract Indicators
            parsed = urlparse(raw_url)
            host = parsed.netloc.split(":")[0].lower() if parsed.netloc else None
            domain = None
            tld = None
            if host:
                parts = host.split(".")
                if len(parts) >= 2:
                    domain = ".".join(parts[-2:])
                    tld = parts[-1]
                else:
                    domain = host

            indicators = ExtractedURLIndicators(
                raw_url=raw_url,
                entropy=features.entropy_full_url,
                has_ip=features.has_ip_in_host,
                domain=domain,
                tld=tld
            )

            result_payload = URLAnalysisResult(
                classification=classification,
                features=features,
                extracted_indicators=indicators
            ).model_dump()

            return URLModelOutputEnvelope(
                schema_version="1.0.0",
                observation_id=obs_id,
                run_id=run_id,
                model=ModelMetadata(
                    name=self._classifier.model_name,
                    version=self._classifier.version,
                    modality="url",
                    execution_hardware=self._hardware,
                    latency_ms=latency_ms
                ),
                status="success",
                created_at=datetime.now(timezone.utc).isoformat(),
                result=result_payload,
                warnings=warnings
            )

        except Exception as e:
            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            return URLModelOutputEnvelope(
                schema_version="1.0.0",
                observation_id=obs_id,
                run_id=run_id,
                model=ModelMetadata(
                    name=self._classifier.model_name,
                    version=self._classifier.version,
                    modality="url",
                    execution_hardware=self._hardware,
                    latency_ms=latency_ms
                ),
                status="error",
                created_at=datetime.now(timezone.utc).isoformat(),
                result={},
                warnings=warnings,
                error_details={
                    "error_type": type(e).__name__,
                    "message": str(e),
                    "stack_trace": None
                }
            )
