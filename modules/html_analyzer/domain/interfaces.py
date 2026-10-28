"""
Interfaces for HTML / NLP Analyzer.
Following Dependency Inversion Principle (DIP).
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from modules.html_analyzer.domain.schemas import DOMFeatures, NLPSignals, HTMLClassification


class IHTMLFeatureExtractor(ABC):
    """Abstract interface for extracting DOM and NLP features from HTML."""

    @abstractmethod
    def extract(self, html_text: str, page_url: str = "") -> Dict[str, Any]:
        """Extract DOM features and NLP signals."""
        pass


class IHTMLClassifier(ABC):
    """Abstract interface for classifying HTML based on extracted features."""

    @abstractmethod
    def classify(self, dom_features: Dict[str, Any], nlp_signals: Dict[str, Any]) -> HTMLClassification:
        """Evaluate DOM and NLP signals to produce a classification verdict."""
        pass
