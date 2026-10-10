"""
URL Feature Extractor & Baseline Scorer
Extracts lexical, structural, and character-entropy indicators from URLs
and produces a risk score baseline using configurable heuristic thresholds.
"""

import math
import re
from typing import Dict, Any, List
from urllib.parse import urlparse


def calculate_shannon_entropy(text: str) -> float:
    """Calculate Shannon character entropy for a given string."""
    if not text:
        return 0.0
    freq = {}
    for char in text:
        freq[char] = freq.get(char, 0) + 1
    length = len(text)
    entropy = 0.0
    for count in freq.values():
        p = count / length
        entropy -= p * math.log2(p)
    return round(entropy, 4)


def extract_url_features(raw_url: str) -> Dict[str, Any]:
    """
    Extract a documented set of lexical and structural features from a URL.
    
    Features:
    - url_length: Total character length of URL
    - host_length: Character length of hostname/netloc
    - path_length: Character length of path component
    - query_length: Character length of query string
    - path_depth: Count of path segments separated by '/'
    - num_digits: Count of numeric digits in full URL
    - num_special_chars: Count of special characters (-_=?&%@!~+)
    - num_hyphens: Count of '-' characters
    - num_subdomains: Number of dot-separated segments in host minus registered domain
    - has_ip_in_host: Whether host is an IPv4 address
    - has_https: Whether scheme is HTTPS
    - has_at_symbol: Whether '@' exists in URL
    - has_double_slash_in_path: Whether '//' occurs in path (open redirect indicator)
    - entropy_full_url: Shannon entropy of full URL string
    - entropy_host: Shannon entropy of host string
    - suspicious_tld: Whether TLD belongs to high-abuse TLD categories (.xyz, .top, .work, .club, etc.)
    """
    if not raw_url:
        return {
            "url_length": 0,
            "host_length": 0,
            "path_length": 0,
            "query_length": 0,
            "path_depth": 0,
            "num_digits": 0,
            "num_special_chars": 0,
            "num_hyphens": 0,
            "num_subdomains": 0,
            "has_ip_in_host": False,
            "has_https": False,
            "has_at_symbol": False,
            "has_double_slash_in_path": False,
            "entropy_full_url": 0.0,
            "entropy_host": 0.0,
            "suspicious_tld": False
        }

    parsed = urlparse(raw_url)
    scheme = (parsed.scheme or "").lower()
    netloc = parsed.netloc or ""
    host = netloc.split(":")[0].lower() if ":" in netloc else netloc.lower()
    path = parsed.path or ""
    query = parsed.query or ""

    # Digits and specials
    num_digits = sum(1 for c in raw_url if c.isdigit())
    special_chars = set("-_=?&%@!~+")
    num_special_chars = sum(1 for c in raw_url if c in special_chars)
    num_hyphens = raw_url.count("-")

    # IP in hostname check
    has_ip = bool(re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", host))

    # Path depth
    path_depth = len([p for p in path.split("/") if p.strip()])

    # Subdomains count
    host_parts = [p for p in host.split(".") if p]
    num_subdomains = max(0, len(host_parts) - 2) if not has_ip else 0

    # High-abuse TLDs
    high_abuse_tlds = {"xyz", "top", "work", "club", "buzz", "gq", "cf", "tk", "ml", "fit", "live", "vip", "icu"}
    tld = host_parts[-1] if host_parts and not has_ip else ""
    suspicious_tld = tld in high_abuse_tlds

    return {
        "url_length": len(raw_url),
        "host_length": len(host),
        "path_length": len(path),
        "query_length": len(query),
        "path_depth": path_depth,
        "num_digits": num_digits,
        "num_special_chars": num_special_chars,
        "num_hyphens": num_hyphens,
        "num_subdomains": num_subdomains,
        "has_ip_in_host": has_ip,
        "has_https": scheme == "https",
        "has_at_symbol": "@" in raw_url,
        "has_double_slash_in_path": "//" in path,
        "entropy_full_url": calculate_shannon_entropy(raw_url),
        "entropy_host": calculate_shannon_entropy(host),
        "suspicious_tld": suspicious_tld
    }


class URLBaselineClassifier:
    """
    Rule-based & statistical feature baseline classifier.
    Computes a risk confidence score based on empirical phishing URL heuristics.
    """

    def __init__(self, phishing_threshold: float = 0.50):
        self.phishing_threshold = phishing_threshold
        self.version = "1.0.0"
        self.model_name = "url_lexical_baseline"

    def predict(self, raw_url: str) -> Dict[str, Any]:
        """Run feature extraction and compute baseline phishing confidence."""
        features = extract_url_features(raw_url)

        # Baseline heuristic risk accumulation
        risk_score = 0.0

        # Heuristic 1: Raw IP host is heavily penalized
        if features["has_ip_in_host"]:
            risk_score += 0.35

        # Heuristic 2: Excessive length (> 75 chars)
        if features["url_length"] > 75:
            risk_score += min(0.20, (features["url_length"] - 75) * 0.002)

        # Heuristic 3: Excessive path depth (> 3)
        if features["path_depth"] >= 4:
            risk_score += 0.15

        # Heuristic 4: Multiple subdomains (e.g. login.paypal.com.evil.com)
        if features["num_subdomains"] >= 2:
            risk_score += 0.15

        # Heuristic 5: Lack of HTTPS (common in older crawls)
        if not features["has_https"]:
            risk_score += 0.10

        # Heuristic 6: Presence of '@' or '//' in path
        if features["has_at_symbol"] or features["has_double_slash_in_path"]:
            risk_score += 0.25

        # Heuristic 7: High entropy in URL or host (> 4.2)
        if features["entropy_full_url"] > 4.3:
            risk_score += 0.10

        # Heuristic 8: Suspicious / high-abuse TLD
        if features["suspicious_tld"]:
            risk_score += 0.20

        # Normalize score to [0.0, 1.0]
        confidence = min(1.0, max(0.0, round(risk_score, 4)))
        is_phishing = confidence >= self.phishing_threshold

        verdict = "phishing" if is_phishing else ("suspicious" if confidence >= 0.35 else "benign")

        return {
            "classification": {
                "is_phishing_predicted": is_phishing,
                "confidence_score": confidence,
                "verdict": verdict
            },
            "features": features,
            "extracted_indicators": {
                "raw_url": raw_url,
                "entropy": features["entropy_full_url"],
                "has_ip": features["has_ip_in_host"]
            }
        }
