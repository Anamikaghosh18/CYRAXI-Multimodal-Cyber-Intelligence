"""
Pairwise Feature Extraction
Extracts similarity features between observation pairs from multiple modalities.
"""

from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse
import difflib


class PairwiseFeatureExtractor:
    """
    Extracts pairwise features between two observations for similarity scoring.

    Handles missing modalities gracefully - missing evidence is not treated
    as a negative match.
    """

    def __init__(self):
        self.observation_cache: Dict[str, Dict] = {}

    def cache_observation(self, obs_id: str, obs_data: Dict) -> None:
        """Cache observation data for feature extraction."""
        self.observation_cache[obs_id] = obs_data

    def extract_features(
        self,
        obs_id_1: str,
        obs_id_2: str,
    ) -> Dict[str, float]:
        """
        Extract pairwise features between two observations.

        Returns a dictionary of feature names to normalized scores [0, 1].
        Missing features are omitted (not set to 0).
        """
        if obs_id_1 not in self.observation_cache or obs_id_2 not in self.observation_cache:
            return {}

        obs1 = self.observation_cache[obs_id_1]
        obs2 = self.observation_cache[obs_id_2]

        features = {}

        # URL features
        url_features = self._extract_url_features(obs1, obs2)
        features.update(url_features)

        # HTML features (if available)
        html_features = self._extract_html_features(obs1, obs2)
        features.update(html_features)

        # OCR features (if available)
        ocr_features = self._extract_ocr_features(obs1, obs2)
        features.update(ocr_features)

        # Screenshot features (if hashes available)
        screenshot_features = self._extract_screenshot_features(obs1, obs2)
        features.update(screenshot_features)

        # Network features
        network_features = self._extract_network_features(obs1, obs2)
        features.update(network_features)

        return features

    def _extract_url_features(self, obs1: Dict, obs2: Dict) -> Dict[str, float]:
        """Extract URL-based similarity features."""
        features = {}
        url1 = obs1.get("url", "")
        url2 = obs2.get("url", "")

        if not url1 or not url2:
            return features

        # Exact match
        features["url_exact_match"] = 1.0 if url1 == url2 else 0.0

        # Domain match
        domain1 = obs1.get("domain") or obs1.get("host", "")
        domain2 = obs2.get("domain") or obs2.get("host", "")
        if domain1 and domain2:
            features["url_domain_match"] = 1.0 if domain1 == domain2 else 0.0

        # Subdomain relationship
        if domain1 and domain2:
            parts1 = domain1.split(".")
            parts2 = domain2.split(".")
            if len(parts1) >= 2 and len(parts2) >= 2:
                # Check if one is subdomain of the other
                reg_domain1 = ".".join(parts1[-2:])
                reg_domain2 = ".".join(parts2[-2:])
                features["url_registered_domain_match"] = 1.0 if reg_domain1 == reg_domain2 else 0.0

        # Token similarity (Jaccard on path segments)
        parsed1 = urlparse(url1)
        parsed2 = urlparse(url2)
        path1 = parsed1.path or ""
        path2 = parsed2.path or ""

        if path1 and path2:
            tokens1 = set(path1.split("/"))
            tokens2 = set(path2.split("/"))
            if tokens1 and tokens2:
                intersection = len(tokens1 & tokens2)
                union = len(tokens1 | tokens2)
                features["url_path_jaccard"] = intersection / union if union > 0 else 0.0

        # Edit distance similarity
        if url1 and url2:
            similarity = difflib.SequenceMatcher(None, url1, url2).ratio()
            features["url_edit_similarity"] = similarity

        return features

    def _extract_html_features(self, obs1: Dict, obs2: Dict) -> Dict[str, float]:
        """Extract HTML-based similarity features."""
        features = {}

        # Check if HTML hashes are available
        html_hash1 = obs1.get("html_hash")
        html_hash2 = obs2.get("html_hash")

        if html_hash1 and html_hash2:
            features["html_hash_match"] = 1.0 if html_hash1 == html_hash2 else 0.0

        # If we have model outputs, we could extract more features
        # For now, return empty if no hashes
        return features

    def _extract_ocr_features(self, obs1: Dict, obs2: Dict) -> Dict[str, float]:
        """Extract OCR-based similarity features."""
        features = {}

        ocr_text1 = obs1.get("ocr_text", "")
        ocr_text2 = obs2.get("ocr_text", "")

        if not ocr_text1 or not ocr_text2:
            return features

        # Lowercase for comparison
        text1 = ocr_text1.lower()
        text2 = ocr_text2.lower()

        # Jaccard similarity on word sets
        words1 = set(text1.split())
        words2 = set(text2.split())

        if words1 and words2:
            intersection = len(words1 & words2)
            union = len(words1 | words2)
            features["ocr_text_jaccard"] = intersection / union if union > 0 else 0.0

        # Shared credential keywords
        keywords1 = obs1.get("ocr_keywords", [])
        keywords2 = obs2.get("ocr_keywords", [])

        if keywords1 and keywords2:
            shared = set(keywords1) & set(keywords2)
            features["ocr_shared_keywords"] = len(shared) / max(len(keywords1), len(keywords2))

        # Shared brand mentions
        brands1 = obs1.get("ocr_brands", [])
        brands2 = obs2.get("ocr_brands", [])

        if brands1 and brands2:
            shared = set(brands1) & set(brands2)
            features["ocr_shared_brands"] = 1.0 if shared else 0.0

        return features

    def _extract_screenshot_features(self, obs1: Dict, obs2: Dict) -> Dict[str, float]:
        """Extract screenshot-based similarity features."""
        features = {}

        # Check for perceptual hashes (would need to be computed elsewhere)
        phash1 = obs1.get("screenshot_phash")
        phash2 = obs2.get("screenshot_phash")

        if phash1 and phash2:
            # Hamming distance would need to be computed
            # For now, just check exact match
            features["screenshot_phash_match"] = 1.0 if phash1 == phash2 else 0.0

        return features

    def _extract_network_features(self, obs1: Dict, obs2: Dict) -> Dict[str, float]:
        """Extract network-based similarity features."""
        features = {}

        # IP match
        ip1 = obs1.get("ip")
        ip2 = obs2.get("ip")

        if ip1 and ip2:
            features["network_ip_match"] = 1.0 if ip1 == ip2 else 0.0

        # ASN match
        asn1 = obs1.get("asn")
        asn2 = obs2.get("asn")

        if asn1 and asn2:
            features["network_asn_match"] = 1.0 if asn1 == asn2 else 0.0

        # Country match
        country1 = obs1.get("country_code")
        country2 = obs2.get("country_code")

        if country1 and country2:
            features["network_country_match"] = 1.0 if country1 == country2 else 0.0

        # Brand match (ground truth)
        brand1 = obs1.get("brand")
        brand2 = obs2.get("brand")

        if brand1 and brand2:
            features["brand_match"] = 1.0 if brand1 == brand2 else 0.0

        # Family ID match (ground truth campaign cluster)
        family1 = obs1.get("family_id")
        family2 = obs2.get("family_id")

        if family1 and family2:
            features["family_id_match"] = 1.0 if family1 == family2 else 0.0

        return features
