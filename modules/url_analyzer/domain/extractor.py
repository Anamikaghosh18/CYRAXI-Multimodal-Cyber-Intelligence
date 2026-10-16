"""
Feature Extractor Implementation — v2 (Enhanced)
Extracts typed, validated URLFeatureSet conforming to IURLFeatureExtractor.

New in v2:
- Brand impersonation / spoofing signals (brand_in_subdomain, brand_in_path)
- IDN / Punycode homoglyph detection (is_punycode_domain, has_non_ascii_chars)
- URL shortener flag (is_url_shortener)
- Percent-encoding obfuscation ratio (percent_encoding_ratio)
- Sensitive phishing keyword density (sensitive_keyword_count)
- Host-to-path length ratio (host_path_length_ratio)
- Domain vowel-to-consonant ratio — anti-DGA signal (domain_vowel_ratio)
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
    freq: dict = {}
    for char in text:
        freq[char] = freq.get(char, 0) + 1
    length = len(text)
    entropy = 0.0
    for count in freq.values():
        p = count / length
        entropy -= p * math.log2(p)
    return round(entropy, 4)


class StandardURLFeatureExtractor(IURLFeatureExtractor):
    """Production implementation of lexical, structural, and anti-spoofing feature extraction."""

    HIGH_ABUSE_TLDS = frozenset([
        "xyz", "top", "work", "club", "buzz", "gq", "cf", "tk", "ml",
        "fit", "live", "vip", "icu", "ga", "cc",
    ])
    SPECIAL_CHARS = frozenset("-_=?&%@!~+")

    # ── Brand token list — top targeted brands ─────────────────────────────
    # Tokens are kept lowercase; checked against subdomain and path components.
    BRAND_TOKENS = frozenset([
        "paypal", "microsoft", "apple", "netflix", "chase", "amazon",
        "google", "facebook", "dhl", "adobe", "wellsfargo", "bankofamerica",
        "instagram", "linkedin", "twitter", "dropbox", "icloud", "coinbase",
    ])

    # ── Known URL shortener domains ────────────────────────────────────────
    URL_SHORTENERS = frozenset([
        "bit.ly", "tinyurl.com", "t.co", "is.gd", "ow.ly",
        "goo.gl", "tiny.cc", "buff.ly", "short.link", "rb.gy",
    ])

    # ── Sensitive phishing keywords ────────────────────────────────────────
    SENSITIVE_KEYWORDS = frozenset([
        "login", "signin", "sign-in", "secure", "account", "verify",
        "update", "banking", "wallet", "security", "recover", "confirm",
        "password", "credential", "auth", "validate", "verification",
    ])

    VOWELS = frozenset("aeiou")
    CONSONANTS = frozenset("bcdfghjklmnpqrstvwxyz")

    def extract(self, raw_url: str) -> URLFeatureSet:
        _empty = URLFeatureSet(
            url_length=0, host_length=0, path_length=0, query_length=0,
            path_depth=0, num_digits=0, num_special_chars=0, num_hyphens=0,
            num_subdomains=0, has_ip_in_host=False, has_https=False,
            has_at_symbol=False, has_double_slash_in_path=False,
            entropy_full_url=0.0, entropy_host=0.0, suspicious_tld=False,
        )
        if not raw_url:
            return _empty

        parsed = urlparse(raw_url)
        scheme = (parsed.scheme or "").lower()
        netloc = parsed.netloc or ""
        host = netloc.split(":")[0].lower() if ":" in netloc else netloc.lower()
        path = parsed.path or ""
        query = parsed.query or ""
        path_and_query = (path + query).lower()

        # ── Basic counts ───────────────────────────────────────────────────
        num_digits = sum(1 for c in raw_url if c.isdigit())
        num_special_chars = sum(1 for c in raw_url if c in self.SPECIAL_CHARS)
        num_hyphens = raw_url.count("-")

        # ── IP host detection ──────────────────────────────────────────────
        has_ip = bool(re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", host))

        # ── Path depth ─────────────────────────────────────────────────────
        path_depth = len([p for p in path.split("/") if p.strip()])

        # ── Subdomains & TLD ───────────────────────────────────────────────
        host_parts = [p for p in host.split(".") if p]
        num_subdomains = max(0, len(host_parts) - 2) if not has_ip else 0
        tld = host_parts[-1] if host_parts and not has_ip else ""
        registered_domain = ".".join(host_parts[-2:]) if len(host_parts) >= 2 else host
        subdomain_part = ".".join(host_parts[:-2]) if num_subdomains > 0 else ""

        suspicious_tld = tld in self.HIGH_ABUSE_TLDS

        # ── Brand impersonation signals ────────────────────────────────────
        brand_in_subdomain = any(tok in subdomain_part for tok in self.BRAND_TOKENS)
        brand_in_path = any(tok in path_and_query for tok in self.BRAND_TOKENS)

        # ── IDN / Punycode homoglyph detection ─────────────────────────────
        is_punycode_domain = "xn--" in host
        try:
            netloc.encode("ascii")
            has_non_ascii_chars = False
        except UnicodeEncodeError:
            has_non_ascii_chars = True

        # ── URL shortener flag ─────────────────────────────────────────────
        is_url_shortener = registered_domain in self.URL_SHORTENERS

        # ── Percent-encoding obfuscation ratio ─────────────────────────────
        pct_matches = re.findall(r"%[0-9a-fA-F]{2}", raw_url)
        url_len = max(1, len(raw_url))
        percent_encoding_ratio = round(len(pct_matches) / url_len, 4)

        # ── Sensitive keyword density ──────────────────────────────────────
        sensitive_keyword_count = sum(
            1 for kw in self.SENSITIVE_KEYWORDS if kw in path_and_query
        )

        # ── Host-to-path length ratio ──────────────────────────────────────
        host_path_length_ratio = round(len(host) / max(1, len(path)), 4)

        # ── Domain vowel ratio (anti-DGA) ──────────────────────────────────
        domain_letters = [c for c in registered_domain.replace(".", "").lower()
                          if c in self.VOWELS or c in self.CONSONANTS]
        if domain_letters:
            vowel_count = sum(1 for c in domain_letters if c in self.VOWELS)
            domain_vowel_ratio = round(vowel_count / len(domain_letters), 4)
        else:
            domain_vowel_ratio = 0.0

        return URLFeatureSet(
            # Original 16
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
            suspicious_tld=suspicious_tld,
            # v2 anti-spoofing / obfuscation
            brand_in_subdomain=brand_in_subdomain,
            brand_in_path=brand_in_path,
            is_punycode_domain=is_punycode_domain,
            has_non_ascii_chars=has_non_ascii_chars,
            is_url_shortener=is_url_shortener,
            percent_encoding_ratio=percent_encoding_ratio,
            sensitive_keyword_count=sensitive_keyword_count,
            host_path_length_ratio=host_path_length_ratio,
            domain_vowel_ratio=domain_vowel_ratio,
        )
