"""
URL Analysis Pipeline Service — v2 (with Explainability)
Orchestrates extraction, model inference, validation, and envelope wrapping.
Follows Single Responsibility Principle (SRP) and Open-Closed Principle (OCP).

New in v2:
- compute_top_risk_factors(): compares feature values against benign baselines
  and returns the top-3 contributing signals in classification.top_risk_factors.
"""

import time
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple
from urllib.parse import urlparse

from modules.url_analyzer.domain.interfaces import IURLFeatureExtractor, IURLClassifier
from modules.url_analyzer.domain.schemas import (
    URLFeatureSet,
    URLModelOutputEnvelope,
    URLAnalysisResult,
    URLClassificationResult,
    ExtractedURLIndicators,
    ModelMetadata,
    WarningItem,
)
from modules.url_analyzer.domain.extractor import StandardURLFeatureExtractor
from modules.url_analyzer.models.heuristic_baseline import HeuristicURLClassifier


# ── Benign baselines for risk-factor scoring ───────────────────────────────
# These approximate typical values for a normal benign URL.
# A feature's "risk score" is how far it deviates from benign expectations.
_BENIGN_BASELINE: Dict[str, Tuple[float, str]] = {
    # (expected benign value, direction_of_risk)
    # direction: "high" = higher is riskier, "low" = lower is riskier, "bool_true" = True is riskier
    "url_length":              (60.0,  "high"),
    "num_subdomains":          (1.0,   "high"),
    "num_hyphens":             (1.0,   "high"),
    "path_depth":              (2.0,   "high"),
    "num_digits":              (3.0,   "high"),
    "entropy_full_url":        (3.5,   "high"),
    "entropy_host":            (3.0,   "high"),
    "has_ip_in_host":          (0.0,   "bool_true"),
    "has_at_symbol":           (0.0,   "bool_true"),
    "has_double_slash_in_path":(0.0,   "bool_true"),
    "suspicious_tld":          (0.0,   "bool_true"),
    "brand_in_subdomain":      (0.0,   "bool_true"),
    "brand_in_path":           (0.0,   "bool_true"),
    "is_punycode_domain":      (0.0,   "bool_true"),
    "has_non_ascii_chars":     (0.0,   "bool_true"),
    "is_url_shortener":        (0.0,   "bool_true"),
    "percent_encoding_ratio":  (0.01,  "high"),
    "sensitive_keyword_count": (0.0,   "high"),
    "host_path_length_ratio":  (5.0,   "high"),
    "domain_vowel_ratio":      (0.4,   "low"),
}

# Human-readable descriptions for the top risk signals exposed to callers
_RISK_DESCRIPTIONS: Dict[str, str] = {
    "has_ip_in_host":           "IP address used instead of domain name",
    "has_at_symbol":            "@ symbol present — credential bypass trick",
    "has_double_slash_in_path": "Double slash in path — redirect obfuscation",
    "suspicious_tld":           "High-abuse top-level domain",
    "brand_in_subdomain":       "Targeted brand name used in subdomain (spoofing)",
    "brand_in_path":            "Targeted brand name used in URL path (spoofing)",
    "is_punycode_domain":       "Punycode / IDN homoglyph domain detected",
    "has_non_ascii_chars":      "Non-ASCII characters in domain (homoglyph attack)",
    "is_url_shortener":         "URL shortener used to hide real destination",
    "sensitive_keyword_count":  "Phishing-related keywords in URL path/query",
    "percent_encoding_ratio":   "High percent-encoding — obfuscation attempt",
    "num_subdomains":           "Unusually high number of subdomain levels",
    "url_length":               "Abnormally long URL",
    "entropy_host":             "High entropy hostname — possible DGA",
    "entropy_full_url":         "High entropy URL — randomised path structure",
    "num_hyphens":              "Excessive hyphens in URL",
    "num_digits":               "Unusually high digit count in URL",
    "domain_vowel_ratio":       "Low vowel ratio in domain — possible DGA/random name",
}


def generate_observation_id(url: str, custom_id: Optional[str] = None) -> str:
    """Generate deterministic canonical observation ID if none provided."""
    if custom_id and custom_id.startswith("obs_") and len(custom_id) == 36:
        return custom_id
    seed = f"adhoc_url:{url}".encode("utf-8")
    return f"obs_{hashlib.md5(seed).hexdigest()}"


def compute_top_risk_factors(features: URLFeatureSet, top_n: int = 3) -> List[str]:
    """
    Score each feature by how far it deviates from a benign baseline.
    Returns the top-N most anomalous feature names with human-readable labels.

    Args:
        features: Extracted URLFeatureSet.
        top_n: Number of top risk factors to return.

    Returns:
        List of descriptive risk-factor strings ordered by risk score (highest first).
    """
    feat_dict = features.model_dump()
    scores: List[Tuple[float, str]] = []

    for feat_name, (baseline, direction) in _BENIGN_BASELINE.items():
        val = feat_dict.get(feat_name, 0.0)

        if direction == "bool_true":
            score = 1.0 if bool(val) else 0.0
        elif direction == "high":
            numeric_val = float(int(val) if isinstance(val, bool) else val)
            score = max(0.0, (numeric_val - baseline) / max(1.0, baseline))
        else:  # "low" — lower than baseline is riskier
            numeric_val = float(int(val) if isinstance(val, bool) else val)
            score = max(0.0, (baseline - numeric_val) / max(0.01, baseline))

        if score > 0.0:
            scores.append((score, feat_name))

    scores.sort(key=lambda x: x[0], reverse=True)
    return [
        _RISK_DESCRIPTIONS.get(name, name)
        for _, name in scores[:top_n]
    ]


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
        warnings: List[WarningItem] = []

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
            classification_raw = self._classifier.predict_features(features)

            # 3. Explainability — inject top risk factors into classification
            top_risk = compute_top_risk_factors(features, top_n=3)
            classification = URLClassificationResult(
                is_phishing_predicted=classification_raw.is_phishing_predicted,
                confidence_score=classification_raw.confidence_score,
                verdict=classification_raw.verdict,
                top_risk_factors=top_risk,
            )

            latency_ms = round((time.perf_counter() - t0) * 1000, 2)

            # 4. Extract Indicators
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
