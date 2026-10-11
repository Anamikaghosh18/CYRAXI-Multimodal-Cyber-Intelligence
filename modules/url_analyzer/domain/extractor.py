"""
Feature Extractor Implementation
Extracts typed, validated URLFeatureSet conforming to IURLFeatureExtractor.
"""

import math
import re
from urllib.parse import urlparse
from modules.url_analyzer.domain.interfaces import IURLFeatureExtractor
from modules.url_analyzer.domain.schemas import URLFeatureSet


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


class StandardURLFeatureExtractor(IURLFeatureExtractor):
    """Production implementation of lexical and structural feature extraction."""

    HIGH_ABUSE_TLDS = frozenset([
        "xyz", "top", "work", "club", "buzz", "gq", "cf", "tk", "ml", "fit", "live", "vip", "icu", "ga", "cc"
    ])
    SPECIAL_CHARS = frozenset("-_=?&%@!~+")

    def extract(self, raw_url: str) -> URLFeatureSet:
        if not raw_url:
            return URLFeatureSet(
                url_length=0,
                host_length=0,
                path_length=0,
                query_length=0,
                path_depth=0,
                num_digits=0,
                num_special_chars=0,
                num_hyphens=0,
                num_subdomains=0,
                has_ip_in_host=False,
                has_https=False,
                has_at_symbol=False,
                has_double_slash_in_path=False,
                entropy_full_url=0.0,
                entropy_host=0.0,
                suspicious_tld=False
            )

        parsed = urlparse(raw_url)
        scheme = (parsed.scheme or "").lower()
        netloc = parsed.netloc or ""
        host = netloc.split(":")[0].lower() if ":" in netloc else netloc.lower()
        path = parsed.path or ""
        query = parsed.query or ""

        num_digits = sum(1 for c in raw_url if c.isdigit())
        num_special_chars = sum(1 for c in raw_url if c in self.SPECIAL_CHARS)
        num_hyphens = raw_url.count("-")

        # IP host check
        has_ip = bool(re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", host))

        # Path depth
        path_depth = len([p for p in path.split("/") if p.strip()])

        # Subdomains
        host_parts = [p for p in host.split(".") if p]
        num_subdomains = max(0, len(host_parts) - 2) if not has_ip else 0

        # High-abuse TLD
        tld = host_parts[-1] if host_parts and not has_ip else ""
        suspicious_tld = tld in self.HIGH_ABUSE_TLDS

        return URLFeatureSet(
            url_length=len(raw_url),
            host_length=len(host),
            path_length=len(path),
            query_length=len(query),
            path_depth=path_depth,
            num_digits=num_digits,
            num_special_chars=num_special_chars,
            num_hyphens=num_hyphens,
            num_subdomains=num_subdomains,
            has_ip_in_host=has_ip,
            has_https=scheme == "https",
            has_at_symbol="@" in raw_url,
            has_double_slash_in_path="//" in path,
            entropy_full_url=calculate_shannon_entropy(raw_url),
            entropy_host=calculate_shannon_entropy(host),
            suspicious_tld=suspicious_tld
        )
