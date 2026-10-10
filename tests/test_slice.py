"""
Focused Unit & Integration Tests for Dataset-to-Model Vertical Slice
Tests:
- Schema validation of generated outputs
- Handling missing URLs & missing artifacts
- Invalid URL string robustness
- Deterministic observation ID generation
- Feature extractor consistency & entropy calculation
"""

import json
import os
import unittest
from pathlib import Path

from modules.dataset_adapter.reader import (
    generate_observation_id,
    parse_url_components,
    record_to_canonical_observation,
)
from modules.url_analyzer.features import (
    calculate_shannon_entropy,
    extract_url_features,
    URLBaselineClassifier,
)
from run_slice import validate_observation_record


class TestDatasetAdapter(unittest.TestCase):

    def test_deterministic_observation_id(self):
        id1 = generate_observation_id("phishpedia_primary", "folder_a")
        id2 = generate_observation_id("phishpedia_primary", "folder_a")
        id3 = generate_observation_id("phishpedia_primary", "folder_b")
        self.assertEqual(id1, id2)
        self.assertNotEqual(id1, id3)
        self.assertTrue(id1.startswith("obs_"))
        self.assertEqual(len(id1), 36)

    def test_parse_url_components(self):
        url = "https://sub.example.co.uk:8080/path/test.html?q=1&v=2"
        comps = parse_url_components(url)
        self.assertEqual(comps["scheme"], "https")
        self.assertEqual(comps["host"], "sub.example.co.uk")
        self.assertEqual(comps["domain"], "example.co.uk")
        self.assertEqual(comps["subdomain"], "sub")
        self.assertEqual(comps["tld"], "co.uk")
        self.assertEqual(comps["port"], 8080)
        self.assertEqual(comps["path"], "/path/test.html")
        self.assertEqual(comps["query"], "q=1&v=2")

    def test_parse_url_empty_or_malformed(self):
        comps = parse_url_components("")
        self.assertEqual(comps["raw"], "")
        self.assertEqual(comps["scheme"], "unknown")
        self.assertIsNone(comps["host"])

    def test_canonical_observation_missing_artifacts(self):
        info = {
            "url": "http://evil.com/login",
            "brand": "PayPal",
            "isotime": "2020-01-01T00:00:00Z"
        }
        # No html.txt and no ocr.txt present
        canonical = record_to_canonical_observation(
            dataset_id="phishpedia_primary",
            source_record_id="PayPal+2020-01-01",
            info_dict=info,
            available_files=["shot.png", "info.txt"],
            source_archive_path="dummy.zip"
        )
        self.assertTrue(canonical["availability"]["has_screenshot"])
        self.assertFalse(canonical["availability"]["has_html"])
        self.assertFalse(canonical["availability"]["has_ocr"])
        self.assertIsNone(canonical["artifacts"]["html"])
        self.assertIsNone(canonical["artifacts"]["ocr"])


class TestURLAnalyzer(unittest.TestCase):

    def setUp(self):
        self.classifier = URLBaselineClassifier()

    def test_shannon_entropy(self):
        # Empty string
        self.assertEqual(calculate_shannon_entropy(""), 0.0)
        # Uniform single char
        self.assertEqual(calculate_shannon_entropy("aaaaaa"), 0.0)
        # Higher complexity string
        ent = calculate_shannon_entropy("abcdef123456!@#$%")
        self.assertGreater(ent, 3.5)

    def test_feature_extraction(self):
        url = "http://192.168.1.1/admin/login/verify.php?token=xyz123"
        feats = extract_url_features(url)
        self.assertTrue(feats["has_ip_in_host"])
        self.assertFalse(feats["has_https"])
        self.assertGreater(feats["path_depth"], 2)
        self.assertGreater(feats["num_digits"], 0)

    def test_feature_extraction_empty_url(self):
        feats = extract_url_features("")
        self.assertEqual(feats["url_length"], 0)
        self.assertFalse(feats["has_ip_in_host"])
        self.assertFalse(feats["suspicious_tld"])

    def test_classifier_predict_high_risk(self):
        # High risk IP with depth and specials
        high_risk_url = "http://192.168.1.100/paypal/login/session/update.php?key=123"
        pred = self.classifier.predict(high_risk_url)
        self.assertIn("classification", pred)
        self.assertIn("confidence_score", pred["classification"])
        self.assertGreaterEqual(pred["classification"]["confidence_score"], 0.40)


class TestPipelineValidation(unittest.TestCase):

    def test_validate_observation_record_clean(self):
        obs = {
            "observation_id": "obs_1234567890abcdef1234567890abcdef",
            "url": {"raw": "https://example.com"},
            "artifacts": {"screenshot": {"relative_path": "shot.png"}}
        }
        warnings = validate_observation_record(obs)
        self.assertEqual(len(warnings), 0)

    def test_validate_observation_record_missing_url(self):
        obs = {
            "observation_id": "obs_1234567890abcdef1234567890abcdef",
            "url": {"raw": ""},
            "artifacts": {"screenshot": {"relative_path": "shot.png"}}
        }
        warnings = validate_observation_record(obs)
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]["code"], "W_MISSING_URL")


if __name__ == "__main__":
    unittest.main()
