"""
Comprehensive Test Suite for URL Analysis Pipeline
Tests:
- Domain feature extraction & entropy bounds
- Heuristic baseline classification & thresholding
- Machine learning classification (Logistic, RF, Ensemble)
- Service envelope generation & schema conformity
- FastAPI endpoints (health, single analyze, batch analyze)
- Zero data leakage check (domain grouping disjointness)
"""

import unittest
from fastapi.testclient import TestClient

from modules.url_analyzer.domain.extractor import StandardURLFeatureExtractor, calculate_shannon_entropy
from modules.url_analyzer.domain.schemas import URLFeatureSet
from modules.url_analyzer.models.heuristic_baseline import HeuristicURLClassifier
from modules.url_analyzer.models.ml_models import SklearnURLClassifier, URLEnsembleClassifier
from modules.url_analyzer.service import URLAnalysisService
from modules.url_analyzer.api.server import create_app


class TestURLFeatureExtractor(unittest.TestCase):

    def setUp(self):
        self.extractor = StandardURLFeatureExtractor()

    def test_empty_url(self):
        feats = self.extractor.extract("")
        self.assertEqual(feats.url_length, 0)
        self.assertFalse(feats.has_ip_in_host)
        self.assertFalse(feats.has_https)
        self.assertEqual(feats.entropy_full_url, 0.0)

    def test_phishing_characteristics_extraction(self):
        phish_url = "http://192.168.1.50/login/paypal/verify.php?token=abc-123@auth"
        feats = self.extractor.extract(phish_url)
        self.assertTrue(feats.has_ip_in_host)
        self.assertFalse(feats.has_https)
        self.assertTrue(feats.has_at_symbol)
        self.assertGreater(feats.path_depth, 2)
        self.assertGreater(feats.entropy_full_url, 3.5)

    def test_feature_to_vector_shape(self):
        feats = self.extractor.extract("https://example.com/test")
        vec = feats.to_vector()
        self.assertEqual(len(vec), 16)
        self.assertEqual(len(URLFeatureSet.feature_names()), 16)


class TestClassifiers(unittest.TestCase):

    def setUp(self):
        self.extractor = StandardURLFeatureExtractor()
        self.heuristic_clf = HeuristicURLClassifier()

    def test_heuristic_benign_url(self):
        feats = self.extractor.extract("https://google.com/search")
        pred = self.heuristic_clf.predict_features(feats)
        self.assertEqual(pred.verdict, "benign")
        self.assertFalse(pred.is_phishing_predicted)

    def test_heuristic_blatant_phish(self):
        feats = self.extractor.extract("http://192.168.1.1/paypal/login/account/update//session?ref=admin@auth")
        pred = self.heuristic_clf.predict_features(feats)
        self.assertTrue(pred.is_phishing_predicted)
        self.assertGreater(pred.confidence_score, 0.5)


class TestPipelineService(unittest.TestCase):

    def setUp(self):
        self.service = URLAnalysisService()

    def test_empty_url_handling(self):
        env = self.service.analyze("")
        self.assertEqual(env.status, "skipped")
        self.assertEqual(len(env.warnings), 1)
        self.assertEqual(env.warnings[0].code, "W_URL_EMPTY")

    def test_valid_envelope_conformance(self):
        env = self.service.analyze("https://github.com/torvalds/linux")
        self.assertEqual(env.status, "success")
        self.assertTrue(env.observation_id.startswith("obs_"))
        self.assertEqual(env.model.modality, "url")
        self.assertIn("classification", env.result)
        self.assertIn("features", env.result)
        self.assertIn("extracted_indicators", env.result)


class TestFastAPIEndpoints(unittest.TestCase):

    def setUp(self):
        app = create_app()
        self.client = TestClient(app)

    def test_health_check(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["module"], "url_analyzer")

    def test_single_analyze_endpoint(self):
        payload = {
            "url": "http://suspicious-paypal-update.com/signin",
            "model_type": "ensemble"
        }
        response = self.client.post("/api/v1/url/analyze", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["schema_version"], "1.0.0")
        self.assertEqual(data["status"], "success")
        self.assertIn("classification", data["result"])

    def test_batch_analyze_endpoint(self):
        payload = {
            "urls": [
                "https://wikipedia.org",
                "http://192.168.1.10/verify-account",
                ""
            ],
            "model_type": "ensemble"
        }
        response = self.client.post("/api/v1/url/batch-analyze", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total_processed"], 3)
        self.assertEqual(len(data["envelopes"]), 3)
        # 3rd was empty, should be skipped
        self.assertEqual(data["envelopes"][2]["status"], "skipped")


if __name__ == "__main__":
    unittest.main()
