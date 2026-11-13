"""
Unit tests for the investigation metrics aggregation logic.
"""

import unittest
from modules.evaluator.metrics import aggregate_investigation_metrics


class TestInvestigationMetricsAggregation(unittest.TestCase):
    def test_empty_reports_list(self):
        res = aggregate_investigation_metrics([])
        self.assertEqual(res["total_investigations"], 0)
        self.assertEqual(res["phishing_rate"], 0.0)
        self.assertEqual(res["top_targeted_brands"], [])

    def test_metrics_calculation_logic(self):
        rep1 = {
            "investigation_id": "inv_001",
            "observation_id": "obs_001",
            "status": "success",
            "runtime_ms": 120.0,
            "overall_assessment": {"verdict": "phishing", "confidence": 0.95},
            "target_brand": "Microsoft",
            "module_results": {
                "url": {"status": "success", "model": {"latency_ms": 15.0}},
                "multimodal_fusion": {
                    "status": "success",
                    "model": {"latency_ms": 5.0},
                    "result": {
                        "classification": {"verdict": "phishing"},
                        "identity_conflict_assessment": {"brand_domain_mismatch_detected": True},
                    },
                },
            },
            "related_observations": [{"id": "obs_2"}],
            "graph_intelligence": {"community": {"cluster_id": "c1"}},
        }

        rep2 = {
            "investigation_id": "inv_002",
            "observation_id": "obs_002",
            "status": "success",
            "runtime_ms": 80.0,
            "overall_assessment": {"verdict": "benign", "confidence": 0.15},
            "target_brand": "PayPal",
            "module_results": {
                "url": {"status": "success", "model": {"latency_ms": 10.0}},
                "multimodal_fusion": {
                    "status": "success",
                    "model": {"latency_ms": 4.0},
                    "result": {
                        "classification": {"verdict": "benign"},
                        "identity_conflict_assessment": {"brand_domain_mismatch_detected": False},
                    },
                },
            },
            "related_observations": [],
            "graph_intelligence": {},
        }

        res = aggregate_investigation_metrics([rep1, rep2])
        self.assertEqual(res["total_investigations"], 2)
        self.assertEqual(res["status_distribution"]["success"], 2)
        self.assertEqual(res["verdict_distribution"]["phishing"], 1)
        self.assertEqual(res["verdict_distribution"]["benign"], 1)
        self.assertEqual(res["phishing_rate"], 0.5)
        self.assertEqual(res["identity_conflict_metrics"]["conflict_count"], 1)
        self.assertEqual(res["identity_conflict_metrics"]["conflict_rate"], 0.5)
        self.assertEqual(len(res["top_targeted_brands"]), 2)
        self.assertAlmostEqual(res["latency_benchmarks"]["end_to_end_pipeline"]["mean_ms"], 100.0)


if __name__ == "__main__":
    unittest.main()
