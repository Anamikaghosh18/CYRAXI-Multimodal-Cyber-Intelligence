"""
Domain Entities and Pydantic Schemas for URL Analysis Module
Adheres to schemas/model-output.schema.json and SOLID domain model principles.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class URLFeatureSet(BaseModel):
    """Documented set of extracted lexical, structural, entropy, and anti-spoofing features."""

    # ── Original 16 lexical / structural features ──────────────────────────
    url_length: int
    host_length: int
    path_length: int
    query_length: int
    path_depth: int
    num_digits: int
    num_special_chars: int
    num_hyphens: int
    num_subdomains: int
    has_ip_in_host: bool
    has_https: bool
    has_at_symbol: bool
    has_double_slash_in_path: bool
    entropy_full_url: float
    entropy_host: float
    suspicious_tld: bool

    # ── Advanced anti-spoofing / brand-abuse features (v2) ─────────────────
    brand_in_subdomain: bool = False        # known brand token present in subdomain
    brand_in_path: bool = False             # known brand token present in URL path
    is_punycode_domain: bool = False        # xn-- IDN / homoglyph domain
    has_non_ascii_chars: bool = False       # non-ASCII chars in netloc
    is_url_shortener: bool = False          # domain is a known URL-shortening service
    percent_encoding_ratio: float = 0.0    # %xx sequences / url_length
    sensitive_keyword_count: int = 0        # count of phishing keywords in path+query
    host_path_length_ratio: float = 0.0    # host_length / max(1, path_length)
    domain_vowel_ratio: float = 0.0        # vowels / (vowels+consonants) in domain

    def to_vector(self) -> List[float]:
        """Convert feature set to ordered numerical vector for ML models."""
        return [
            # original 16
            float(self.url_length),
            float(self.host_length),
            float(self.path_length),
            float(self.query_length),
            float(self.path_depth),
            float(self.num_digits),
            float(self.num_special_chars),
            float(self.num_hyphens),
            float(self.num_subdomains),
            1.0 if self.has_ip_in_host else 0.0,
            1.0 if self.has_https else 0.0,
            1.0 if self.has_at_symbol else 0.0,
            1.0 if self.has_double_slash_in_path else 0.0,
            self.entropy_full_url,
            self.entropy_host,
            1.0 if self.suspicious_tld else 0.0,
            # v2 anti-spoofing / obfuscation
            1.0 if self.brand_in_subdomain else 0.0,
            1.0 if self.brand_in_path else 0.0,
            1.0 if self.is_punycode_domain else 0.0,
            1.0 if self.has_non_ascii_chars else 0.0,
            1.0 if self.is_url_shortener else 0.0,
            self.percent_encoding_ratio,
            float(self.sensitive_keyword_count),
            self.host_path_length_ratio,
            self.domain_vowel_ratio,
        ]

    @classmethod
    def feature_names(cls) -> List[str]:
        return [
            # original 16
            "url_length",
            "host_length",
            "path_length",
            "query_length",
            "path_depth",
            "num_digits",
            "num_special_chars",
            "num_hyphens",
            "num_subdomains",
            "has_ip_in_host",
            "has_https",
            "has_at_symbol",
            "has_double_slash_in_path",
            "entropy_full_url",
            "entropy_host",
            "suspicious_tld",
            # v2 anti-spoofing / obfuscation
            "brand_in_subdomain",
            "brand_in_path",
            "is_punycode_domain",
            "has_non_ascii_chars",
            "is_url_shortener",
            "percent_encoding_ratio",
            "sensitive_keyword_count",
            "host_path_length_ratio",
            "domain_vowel_ratio",
        ]


class URLClassificationResult(BaseModel):
    is_phishing_predicted: bool
    confidence_score: float = Field(ge=0.0, le=1.0)
    verdict: str = Field(pattern="^(phishing|suspicious|benign)$")
    top_risk_factors: List[str] = Field(
        default_factory=list,
        description="Top contributing risk signals, e.g. ['brand_in_path', 'has_ip_in_host']"
    )


class ExtractedURLIndicators(BaseModel):
    raw_url: str
    entropy: float
    has_ip: bool
    domain: Optional[str] = None
    tld: Optional[str] = None


class URLAnalysisResult(BaseModel):
    classification: URLClassificationResult
    features: URLFeatureSet
    extracted_indicators: ExtractedURLIndicators


class WarningItem(BaseModel):
    code: str
    message: str
    artifact_ref: Optional[str] = None


class ErrorDetails(BaseModel):
    error_type: str
    message: str
    stack_trace: Optional[str] = None


class ModelMetadata(BaseModel):
    name: str
    version: str
    modality: str = "url"
    execution_hardware: str = "cpu"
    latency_ms: float = 0.0


class URLModelOutputEnvelope(BaseModel):
    """The canonical model output envelope matching schemas/model-output.schema.json."""
    schema_version: str = "1.0.0"
    observation_id: str = Field(pattern="^obs_[a-f0-9]{32}$")
    run_id: str
    model: ModelMetadata
    status: str = Field(pattern="^(success|partial|skipped|error)$")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    result: Optional[Dict[str, Any]] = None
    warnings: List[WarningItem] = Field(default_factory=list)
    error_details: Optional[ErrorDetails] = None


# HTTP Request & Response Models for Backend Integration
class AnalyzeURLRequest(BaseModel):
    url: str
    observation_id: Optional[str] = None
    run_id: Optional[str] = "api_ad_hoc_run"
    model_type: Optional[str] = "ensemble"  # "baseline", "random_forest", "logistic", "ensemble"


class BatchAnalyzeRequest(BaseModel):
    urls: List[str]
    run_id: Optional[str] = "batch_api_run"
    model_type: Optional[str] = "ensemble"


class BatchAnalyzeResponse(BaseModel):
    total_processed: int
    duration_ms: float
    envelopes: List[URLModelOutputEnvelope]
