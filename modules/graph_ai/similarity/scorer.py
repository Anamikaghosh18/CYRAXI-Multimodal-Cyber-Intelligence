"""
Similarity Scorer
Computes explainable similarity scores between observation pairs using
weighted combination of extracted features.
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
import yaml


class SimilarityScorer:
    """
    Computes similarity scores between observation pairs.

    Scores are weighted combinations of available features with
    transparent contribution tracking.
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize similarity scorer with configuration.

        Args:
            config_path: Path to YAML config file with feature weights
        """
        self.config = self._load_config(config_path)
        self.feature_weights = self.config.get("feature_weights", {})

    def _load_config(self, config_path: Optional[str]) -> Dict:
        """Load configuration from YAML file or use defaults."""
        default_config = {
            "feature_weights": {
                "url_exact_match": 1.0,
                "url_domain_match": 0.8,
                "url_registered_domain_match": 0.6,
                "url_path_jaccard": 0.3,
                "url_edit_similarity": 0.4,
                "html_hash_match": 0.9,
                "ocr_text_jaccard": 0.5,
                "ocr_shared_keywords": 0.7,
                "ocr_shared_brands": 0.8,
                "screenshot_phash_match": 0.9,
                "network_ip_match": 0.7,
                "network_asn_match": 0.5,
                "network_country_match": 0.3,
                "brand_match": 0.2,  # Low weight because popular brands produce many false positives
                "family_id_match": 0.0,  # Exclude from scoring (ground truth)
            },
            "hard_constraints": {
                "different_brand_max_score": 0.5,  # Max score if brands differ
            },
            "thresholds": {
                "candidate": 0.3,
                "review": 0.6,
                "high_similarity": 0.8,
            },
        }

        if config_path:
            try:
                with open(config_path, "r") as f:
                    user_config = yaml.safe_load(f)
                    # Merge user config with defaults
                    if "feature_weights" in user_config:
                        default_config["feature_weights"].update(user_config["feature_weights"])
                    if "hard_constraints" in user_config:
                        default_config["hard_constraints"].update(user_config["hard_constraints"])
                    if "thresholds" in user_config:
                        default_config["thresholds"].update(user_config["thresholds"])
            except Exception:
                pass  # Use defaults if config loading fails

        return default_config

    def compute_similarity(
        self,
        obs_id_1: str,
        obs_id_2: str,
        features: Dict[str, float],
        obs_data_1: Optional[Dict] = None,
        obs_data_2: Optional[Dict] = None,
    ) -> Dict:
        """
        Compute similarity score for a pair of observations.

        Args:
            obs_id_1: First observation ID
            obs_id_2: Second observation ID
            features: Dictionary of feature names to scores [0, 1]
            obs_data_1: First observation data (for constraints)
            obs_data_2: Second observation data (for constraints)

        Returns:
            Dictionary with similarity score, explanation, and metadata
        """
        # Apply hard constraints
        if obs_data_1 and obs_data_2:
            constraint_score = self._apply_hard_constraints(obs_data_1, obs_data_2)
            if constraint_score is not None:
                # Hard constraint violated
                return {
                    "observation_id_1": obs_id_1,
                    "observation_id_2": obs_id_2,
                    "similarity_score": constraint_score,
                    "category": "low",
                    "contributing_features": [],
                    "explanation": "Hard constraint applied",
                    "constraint_applied": True,
                    "algorithm_version": "1.0.0",
                    "computed_at": datetime.now(timezone.utc).isoformat(),
                }

        # Compute weighted score
        total_weight = 0.0
        weighted_sum = 0.0
        contributing_features = []

        for feature_name, feature_value in features.items():
            weight = self.feature_weights.get(feature_name, 0.0)
            if weight > 0 and feature_value > 0:
                contribution = weight * feature_value
                weighted_sum += contribution
                total_weight += weight
                contributing_features.append({
                    "feature": feature_name,
                    "value": feature_value,
                    "weight": weight,
                    "contribution": contribution,
                })

        # Normalize score
        if total_weight > 0:
            similarity_score = weighted_sum / total_weight
        else:
            similarity_score = 0.0

        # Determine category
        thresholds = self.config.get("thresholds", {})
        if similarity_score >= thresholds.get("high_similarity", 0.8):
            category = "high"
        elif similarity_score >= thresholds.get("review", 0.6):
            category = "review"
        elif similarity_score >= thresholds.get("candidate", 0.3):
            category = "candidate"
        else:
            category = "low"

        # Sort contributing features by contribution
        contributing_features.sort(key=lambda x: x["contribution"], reverse=True)

        return {
            "observation_id_1": obs_id_1,
            "observation_id_2": obs_id_2,
            "similarity_score": round(similarity_score, 4),
            "category": category,
            "contributing_features": contributing_features,
            "explanation": self._generate_explanation(contributing_features, category),
            "constraint_applied": False,
            "algorithm_version": "1.0.0",
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }

    def _apply_hard_constraints(
        self,
        obs_data_1: Dict,
        obs_data_2: Dict,
    ) -> Optional[float]:
        """
        Apply hard constraints that limit maximum possible similarity.

        Returns the constrained max score if a constraint applies,
        or None if no constraint applies.
        """
        constraints = self.config.get("hard_constraints", {})

        # Different brands constraint
        brand1 = obs_data_1.get("brand")
        brand2 = obs_data_2.get("brand")

        if brand1 and brand2 and brand1 != brand2:
            max_score = constraints.get("different_brand_max_score")
            if max_score is not None:
                return max_score

        return None

    def _generate_explanation(
        self,
        contributing_features: List[Dict],
        category: str,
    ) -> str:
        """Generate human-readable explanation of the similarity score."""
        if not contributing_features:
            return "No significant shared features detected."

        top_features = contributing_features[:3]
        feature_names = [f["feature"] for f in top_features]

        explanation = f"Similarity based on: {', '.join(feature_names)}"
        if category == "high":
            explanation += " (strong evidence)"
        elif category == "review":
            explanation += " (moderate evidence)"
        elif category == "candidate":
            explanation += " (weak evidence)"

        return explanation
