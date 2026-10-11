"""
Baseline Heuristic Rule-Based Classifier
Implements IURLClassifier interface without requiring trained weights.
"""

from modules.url_analyzer.domain.interfaces import IURLClassifier
from modules.url_analyzer.domain.schemas import URLFeatureSet, URLClassificationResult


class HeuristicURLClassifier(IURLClassifier):
    """
    Expert-heuristic baseline classifier.
    Computes an empirical risk confidence score across 8 security heuristics.
    """

    def __init__(self, phishing_threshold: float = 0.50):
        self._phishing_threshold = phishing_threshold
        self._model_name = "url_heuristic_baseline"
        self._version = "1.0.0"

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def version(self) -> str:
        return self._version

    def predict_features(self, features: URLFeatureSet) -> URLClassificationResult:
        risk_score = 0.0

        if features.has_ip_in_host:
            risk_score += 0.35

        if features.url_length > 75:
            risk_score += min(0.20, (features.url_length - 75) * 0.002)

        if features.path_depth >= 4:
            risk_score += 0.15

        if features.num_subdomains >= 2:
            risk_score += 0.15

        if not features.has_https:
            risk_score += 0.10

        if features.has_at_symbol or features.has_double_slash_in_path:
            risk_score += 0.25

        if features.entropy_full_url > 4.3:
            risk_score += 0.10

        if features.suspicious_tld:
            risk_score += 0.20

        confidence = min(1.0, max(0.0, round(risk_score, 4)))
        is_phishing = confidence >= self._phishing_threshold
        verdict = "phishing" if is_phishing else ("suspicious" if confidence >= 0.35 else "benign")

        return URLClassificationResult(
            is_phishing_predicted=is_phishing,
            confidence_score=confidence,
            verdict=verdict
        )
