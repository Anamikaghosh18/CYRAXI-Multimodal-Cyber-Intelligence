import re
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

from bs4 import BeautifulSoup


def analyze_html(observation_id, run_id, html_text, page_url=""):
    started = time.perf_counter()
    warnings = []

    if not html_text:
        return {
            "schema_version": "1.0.0",
            "observation_id": observation_id,
            "run_id": run_id,
            "model": {
                "name": "html_nlp_detector",
                "version": "1.0.0",
                "modality": "html_nlp",
                "execution_hardware": "cpu",
                "latency_ms": 0.0,
            },
            "status": "skipped",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "result": {},
            "warnings": [{
                "code": "W_HTML_MISSING",
                "message": "HTML artifact was not captured for observation",
                "artifact_ref": "artifacts.html",
            }],
            "error_details": None,
        }

    soup = BeautifulSoup(html_text, "html.parser")
    title_tag = soup.find("title")
    title = title_tag.get_text(" ", strip=True) if title_tag else ""

    forms = []
    for form in soup.find_all("form"):
        action = form.get("action", "")
        inputs = form.find_all("input")
        has_password = any(
            item.get("type", "").lower() == "password"
            for item in inputs
        )

        page_host = urlparse(page_url).hostname or ""
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
        and urlparse(link["href"]).hostname !=
            (urlparse(page_url).hostname or "")
    )

    empty_anchors = sum(
        1 for link in soup.find_all("a")
        if not link.get_text(" ", strip=True)
    )

    text = soup.get_text(" ", strip=True).lower()
    urgency_words = [
        word for word in
        ("urgent", "verify", "suspended", "immediately",
         "password", "login", "confirm", "account")
        if word in text
    ]

    password_form = any(
        form["has_password_input"] for form in forms
    )

    # Transparent baseline heuristic, not a trained classifier.
    signals = int(password_form) + int(bool(urgency_words))
    confidence = min(0.95, 0.35 + 0.25 * signals)
    predicted = signals >= 2

    elapsed = round((time.perf_counter() - started) * 1000, 2)

    return {
        "schema_version": "1.0.0",
        "observation_id": observation_id,
        "run_id": run_id,
        "model": {
            "name": "html_nlp_detector",
            "version": "1.0.0",
            "modality": "html_nlp",
            "execution_hardware": "cpu",
            "latency_ms": elapsed,
        },
        "status": "success",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "result": {
            "classification": {
                "is_phishing_predicted": predicted,
                "confidence_score": confidence,
                "verdict": "phishing" if predicted else "not_phishing",
            },
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
                "credential_harvesting_intent_score": confidence,
                "brand_mentions": [],
            },
        },
        "warnings": warnings,
        "error_details": None,
    }
