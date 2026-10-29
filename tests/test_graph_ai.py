"""
Tests for Graph AI Modules
"""

import unittest
from unittest.mock import MagicMock, patch

from modules.graph_ai.candidate_generation.strategy import CandidateGenerator
from modules.graph_ai.feature_extraction.pairwise_features import PairwiseFeatureExtractor
from modules.graph_ai.similarity.scorer import SimilarityScorer


class TestCandidateGenerator(unittest.TestCase):
    def setUp(self):
        self.gen = CandidateGenerator(
            max_candidates_per_obs=10,
            use_domain_index=True,
            use_ip_index=True,
            use_brand_index=True,
        )

    def test_add_observation(self):
        self.gen.add_observation("obs_1", {
            "url": "http://example.com",
            "domain": "example.com",
            "ip": "1.2.3.4",
            "brand": "TestBrand",
        })
        self.assertEqual(len(self.gen.observation_data), 1)
        self.assertIn("example.com", self.gen.domain_index)
        self.assertIn("1.2.3.4", self.gen.ip_index)
        self.assertIn("TestBrand", self.gen.brand_index)

    def test_generate_candidates_shared_domain(self):
        self.gen.add_observation("obs_1", {"domain": "example.com", "ip": "1.2.3.4"})
        self.gen.add_observation("obs_2", {"domain": "example.com", "ip": "5.6.7.8"})

        candidates = list(self.gen.generate_candidates("obs_1"))
        self.assertGreater(len(candidates), 0)

        methods = [c[2] for c in candidates]
        self.assertIn("shared_domain", methods)

    def test_statistics(self):
        self.gen.add_observation("obs_1", {"domain": "example.com", "ip": "1.2.3.4", "brand": "BrandA"})
        self.gen.add_observation("obs_2", {"domain": "example.com", "ip": "5.6.7.8", "brand": "BrandB"})

        stats = self.gen.get_statistics()
        self.assertEqual(stats["total_observations"], 2)
        self.assertEqual(stats["unique_domains"], 1)
        self.assertEqual(stats["unique_ips"], 2)
        self.assertEqual(stats["unique_brands"], 2)


class TestPairwiseFeatureExtractor(unittest.TestCase):
    def setUp(self):
        self.extractor = PairwiseFeatureExtractor()
        self.extractor.cache_observation("obs_1", {
            "url": "http://example.com/login",
            "domain": "example.com",
            "ip": "1.2.3.4",
            "brand": "TestBrand",
        })
        self.extractor.cache_observation("obs_2", {
            "url": "http://example.com/login",
            "domain": "example.com",
            "ip": "1.2.3.4",
            "brand": "TestBrand",
        })

    def test_extract_url_features(self):
        features = self.extractor.extract_features("obs_1", "obs_2")
        self.assertIn("url_exact_match", features)
        self.assertEqual(features["url_exact_match"], 1.0)
        self.assertIn("url_domain_match", features)
        self.assertEqual(features["url_domain_match"], 1.0)

    def test_extract_different_urls(self):
        self.extractor.cache_observation("obs_3", {
            "url": "http://different.com",
            "domain": "different.com",
        })
        features = self.extractor.extract_features("obs_1", "obs_3")
        self.assertEqual(features["url_exact_match"], 0.0)
        self.assertEqual(features["url_domain_match"], 0.0)


class TestSimilarityScorer(unittest.TestCase):
    def setUp(self):
        self.scorer = SimilarityScorer()

    def test_compute_similarity_high_score(self):
        features = {
            "url_exact_match": 1.0,
            "url_domain_match": 1.0,
            "network_ip_match": 1.0,
        }
        result = self.scorer.compute_similarity("obs_1", "obs_2", features)
        self.assertGreater(result["similarity_score"], 0.5)
        self.assertIn("contributing_features", result)
        self.assertIn("explanation", result)

    def test_compute_similarity_low_score(self):
        features = {
            "url_exact_match": 0.0,
            "url_domain_match": 0.0,
        }
        result = self.scorer.compute_similarity("obs_1", "obs_2", features)
        self.assertLess(result["similarity_score"], 0.5)
        self.assertEqual(result["category"], "low")

    def test_hard_constraint_different_brands(self):
        obs_data_1 = {"brand": "BrandA"}
        obs_data_2 = {"brand": "BrandB"}
        features = {"url_exact_match": 1.0}

        result = self.scorer.compute_similarity(
            "obs_1", "obs_2", features, obs_data_1, obs_data_2
        )
        self.assertTrue(result["constraint_applied"])
        self.assertLessEqual(result["similarity_score"], 0.5)


if __name__ == "__main__":
    unittest.main()
