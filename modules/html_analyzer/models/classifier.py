"""
Heuristic HTML / NLP Classifier.
Evaluates password forms and urgent linguistics.
"""

from typing import Dict, Any
from modules.html_analyzer.domain.interfaces import IHTMLClassifier
from modules.html_analyzer.domain.schemas import HTMLClassification


class HeuristicHTMLClassifier(IHTMLClassifier):
    """Rule-based heuristic classifier conforming to CYRAXI contract."""

    def classify(self, dom_features: Dict[str, Any], nlp_signals: Dict[str, Any]) -> HTMLClassification:
        forms = dom_features.get("forms", [])
        has_password = any(f.get("has_password_input") for f in forms if isinstance(f, dict))
        urgency_cues = nlp_signals.get("urgency_cues", [])

        signals = int(has_password) + int(bool(urgency_cues))
        confidence = min(0.95, 0.35 + 0.25 * signals)
        predicted = signals >= 2

        return HTMLClassification(
            is_phishing_predicted=predicted,
            confidence_score=confidence,
            verdict="phishing" if predicted else "not_phishing"
        )
