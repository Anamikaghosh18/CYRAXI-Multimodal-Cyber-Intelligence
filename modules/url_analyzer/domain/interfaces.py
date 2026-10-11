"""
Abstract Interfaces for URL Classifiers & Extractors
Following Dependency Inversion Principle (DIP) and Open-Closed Principle (OCP).
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
from modules.url_analyzer.domain.schemas import URLFeatureSet, URLClassificationResult


class IURLFeatureExtractor(ABC):
    """Interface for extracting feature representations from raw URLs."""

    @abstractmethod
    def extract(self, raw_url: str) -> URLFeatureSet:
        """Extract typed feature set from URL string."""
        pass


class IURLClassifier(ABC):
    """Interface for URL classification models."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Name of the model module."""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """Semantic version of the model."""
        pass

    @abstractmethod
    def predict_features(self, features: URLFeatureSet) -> URLClassificationResult:
        """Predict classification given extracted feature set."""
        pass
