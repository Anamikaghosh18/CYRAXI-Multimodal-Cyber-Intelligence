"""
HTML DOM and NLP Feature Extractor implementation.
Single Responsibility: Parse HTML DOM and extract structural/NLP cues.
"""

import re
from urllib.parse import urlparse
from typing import Dict, Any, List
from bs4 import BeautifulSoup

from modules.html_analyzer.domain.interfaces import IHTMLFeatureExtractor


class StandardHTMLFeatureExtractor(IHTMLFeatureExtractor):
    """Standard BeautifulSoup based extractor for HTML DOM and linguistic urgency cues."""

    URGENCY_KEYWORDS = (
        "urgent", "verify", "suspended", "immediately",
        "password", "login", "confirm", "account"
    )

    def extract(self, html_text: str, page_url: str = "") -> Dict[str, Any]:
        if not html_text:
            return {
                "dom_features": {
                    "title": "",
                    "meta_tags_count": 0,
                    "form_action_count": 0,
                    "forms": [],
                    "external_links_ratio": 0.0,
                    "empty_anchor_ratio": 0.0,
                    "has_obfuscated_javascript": False,
                    "iframe_count": 0,
                },
                "nlp_signals": {
                    "urgency_cues": [],
                    "credential_harvesting_intent_score": 0.0,
                    "brand_mentions": [],
                }
            }

        soup = BeautifulSoup(html_text, "html.parser")
        title_tag = soup.find("title")
        title = title_tag.get_text(" ", strip=True) if title_tag else ""

        page_host = urlparse(page_url).hostname or ""

        forms = []
        for form in soup.find_all("form"):
            action = form.get("action", "")
            inputs = form.find_all("input")
            has_password = any(
                item.get("type", "").lower() == "password"
                for item in inputs
            )

            action_host = urlparse(action).hostname or ""
            external = bool(action_host and action_host != page_host)

            forms.append({
                "action": action,
                "method": form.get("method", "GET").upper(),
                "has_password_input": has_password,
                "is_action_external": external,
            })

        links = soup.find_all("a", href=True)
        external_links = sum(
            1 for link in links
            if (urlparse(link["href"]).hostname or "")
            and urlparse(link["href"]).hostname != page_host
        )

        empty_anchors = sum(
            1 for link in soup.find_all("a")
            if not link.get_text(" ", strip=True)
        )

        text = soup.get_text(" ", strip=True).lower()
        urgency_words = [
            word for word in self.URGENCY_KEYWORDS
            if word in text
        ]

        # Transparent heuristic signal for intent
        password_form = any(form["has_password_input"] for form in forms)
        signals = int(password_form) + int(bool(urgency_words))
        intent_score = min(0.95, 0.35 + 0.25 * signals)

        return {
            "dom_features": {
                "title": title,
                "meta_tags_count": len(soup.find_all("meta")),
                "form_action_count": len(forms),
                "forms": forms,
                "external_links_ratio": (
                    external_links / len(links) if links else 0.0
                ),
                "empty_anchor_ratio": (
                    empty_anchors / len(soup.find_all("a"))
                    if soup.find_all("a") else 0.0
                ),
                "has_obfuscated_javascript": bool(
                    re.search(r"eval\s*\(|atob\s*\(", html_text)
                ),
                "iframe_count": len(soup.find_all("iframe")),
            },
            "nlp_signals": {
                "urgency_cues": urgency_words,
                "credential_harvesting_intent_score": intent_score,
                "brand_mentions": [],
            }
        }
