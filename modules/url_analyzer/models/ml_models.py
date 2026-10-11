"""
Machine Learning Classifiers for URL Analysis
Implements Logistic Regression, Random Forest, and Calibrated Soft-Voting Ensemble.
"""

import os
from typing import Optional, List, Tuple
import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler

from modules.url_analyzer.domain.interfaces import IURLClassifier
from modules.url_analyzer.domain.schemas import URLFeatureSet, URLClassificationResult


class SklearnURLClassifier(IURLClassifier):
    """Base wrapper for Scikit-Learn classifiers implementing IURLClassifier."""

    def __init__(
        self,
        estimator,
        model_name: str,
        version: str = "1.0.0",
        scaler: Optional[StandardScaler] = None,
        phishing_threshold: float = 0.50
    ):
        self._estimator = estimator
        self._model_name = model_name
        self._version = version
        self._scaler = scaler
        self._phishing_threshold = phishing_threshold

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def version(self) -> str:
        return self._version

    def predict_features(self, features: URLFeatureSet) -> URLClassificationResult:
        vec = np.array([features.to_vector()], dtype=np.float64)
        if self._scaler is not None:
            vec = self._scaler.transform(vec)

        # Predict probability
        if hasattr(self._estimator, "predict_proba"):
            probs = self._estimator.predict_proba(vec)[0]
            # Class 1 is phishing
            confidence = float(probs[1]) if len(probs) > 1 else float(probs[0])
        else:
            pred = self._estimator.predict(vec)[0]
            confidence = 1.0 if pred == 1 else 0.0

        confidence = round(confidence, 4)
        is_phishing = confidence >= self._phishing_threshold
        verdict = "phishing" if is_phishing else ("suspicious" if confidence >= 0.35 else "benign")

        return URLClassificationResult(
            is_phishing_predicted=is_phishing,
            confidence_score=confidence,
            verdict=verdict
        )

    def save(self, filepath: str) -> None:
        """Serialize model and scaler to disk."""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        payload = {
            "estimator": self._estimator,
            "scaler": self._scaler,
            "model_name": self._model_name,
            "version": self._version,
            "phishing_threshold": self._phishing_threshold,
        }
        joblib.dump(payload, filepath)

    @classmethod
    def load(cls, filepath: str) -> "SklearnURLClassifier":
        """Deserialize trained model from disk."""
        payload = joblib.load(filepath)
        return cls(
            estimator=payload["estimator"],
            model_name=payload["model_name"],
            version=payload.get("version", "1.0.0"),
            scaler=payload.get("scaler"),
            phishing_threshold=payload.get("phishing_threshold", 0.50),
        )


class URLEnsembleClassifier(IURLClassifier):
    """
    Weighted Soft-Voting Ensemble Classifier combining Heuristics,
    Logistic Regression, and Random Forest.
    """

    def __init__(
        self,
        classifiers: List[Tuple[IURLClassifier, float]],
        model_name: str = "url_multimodel_ensemble",
        version: str = "1.0.0",
        phishing_threshold: float = 0.50
    ):
        self._classifiers = classifiers
        self._model_name = model_name
        self._version = version
        self._phishing_threshold = phishing_threshold

        # Normalize weights
        total_w = sum(w for _, w in classifiers)
        self._weights = [(clf, w / total_w) for clf, w in classifiers]

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def version(self) -> str:
        return self._version

    def predict_features(self, features: URLFeatureSet) -> URLClassificationResult:
        weighted_conf = 0.0
        for clf, w in self._weights:
            res = clf.predict_features(features)
            weighted_conf += res.confidence_score * w

        confidence = round(min(1.0, max(0.0, weighted_conf)), 4)
        is_phishing = confidence >= self._phishing_threshold
        verdict = "phishing" if is_phishing else ("suspicious" if confidence >= 0.35 else "benign")

        return URLClassificationResult(
            is_phishing_predicted=is_phishing,
            confidence_score=confidence,
            verdict=verdict
        )
