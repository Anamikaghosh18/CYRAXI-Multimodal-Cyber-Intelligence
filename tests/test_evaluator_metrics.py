"""
Unit tests for the CYRAXI Evaluator & Metrics Framework
Module 8: Evaluation & Reporting Dashboard
"""

import math
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
import json

from modules.evaluator.metrics import (
    ClassificationMetrics,
    LatencyMetrics,
    MultimodalMetrics,
    compute_classification_metrics,
    compute_latency_metrics,
    compute_multimodal_metrics,
    compute_graph_metrics,
    MultimodalEvaluator,
)


class TestEvaluatorMetrics(unittest.TestCase):
    def test_classification_metrics_perfect(self):
        y_true = [1, 1, 0, 0]
        y_pred = [1, 1, 0, 0]
        y_prob = [0.99, 0.95, 0.05, 0.01]

        m = compute_classification_metrics(y_true, y_pred, y_prob)
        self.assertEqual(m.total_samples, 4)
        self.assertEqual(m.accuracy, 1.0)
        self.assertEqual(m.precision, 1.0)
        self.assertEqual(m.recall, 1.0)
        self.assertEqual(m.specificity, 1.0)
        self.assertEqual(m.f1_score, 1.0)
        self.assertEqual(m.balanced_accuracy, 1.0)
        self.assertEqual(m.false_positive_rate, 0.0)
        self.assertEqual(m.false_negative_rate, 0.0)
        self.assertEqual(m.roc_auc, 1.0)
        self.assertAlmostEqual(m.pr_auc, 1.0, places=4)
        self.assertLess(m.brier_score, 0.01)
        self.assertLess(m.expected_calibration_error, 0.1)

    def test_classification_metrics_edge_cases(self):
        # Empty inputs
        empty = compute_classification_metrics([], [])
        self.assertEqual(empty.total_samples, 0)
        self.assertEqual(empty.accuracy, 0.0)

        # All positive ground truth
        all_pos = compute_classification_metrics([1, 1], [1, 0])
        self.assertEqual(all_pos.precision, 1.0)
        self.assertEqual(all_pos.recall, 0.5)
        self.assertEqual(all_pos.specificity, 0.0)

        # All negative ground truth
        all_neg = compute_classification_metrics([0, 0], [0, 0])
        self.assertEqual(all_neg.accuracy, 1.0)
        self.assertEqual(all_neg.recall, 0.0)
        self.assertEqual(all_neg.specificity, 1.0)

    def test_latency_metrics(self):
        # Empty
        lat_empty = compute_latency_metrics([])
        self.assertEqual(lat_empty.count, 0)
        self.assertEqual(lat_empty.mean_ms, 0.0)

        # Normal latencies
        latencies = [10.0, 20.0, 30.0, 40.0, 50.0]
        lat = compute_latency_metrics(latencies)
        self.assertEqual(lat.count, 5)
        self.assertAlmostEqual(lat.mean_ms, 30.0)
        self.assertAlmostEqual(lat.median_ms, 30.0)
        self.assertEqual(lat.min_ms, 10.0)
        self.assertEqual(lat.max_ms, 50.0)
        self.assertGreater(lat.throughput_rps, 0.0)
        self.assertAlmostEqual(lat.p90_ms, 46.0, places=1)

    def test_multimodal_metrics_and_lift(self):
        sample_reports = [
            {
                "observation_id": "obs_001",
                "module_results": {
                    "url": {
                        "status": "success",
                        "result": {"classification": {"is_phishing_predicted": True}},
                    },
                    "html_nlp": {
                        "status": "success",
                        "result": {"classification": {"is_phishing_predicted": True}},
                    },
                    "multimodal_fusion": {
                        "status": "success",
                        "result": {
                            "classification": {"is_phishing_predicted": True, "confidence_score": 0.95},
                            "identity_conflict_assessment": {"brand_domain_mismatch_detected": True},
                            "supporting_evidence": [
                                {"modality": "url", "score": 0.8},
                                {"modality": "html_nlp", "score": 0.9},
                            ],
                        },
                    },
                },
            },
            {
                "observation_id": "obs_002",
                "module_results": {
                    "url": {
                        "status": "success",
                        "result": {"classification": {"is_phishing_predicted": False}},
                    },
                    "html_nlp": {
                        "status": "skipped",
                    },
                    "multimodal_fusion": {
                        "status": "partial",
                        "result": {
                            "classification": {"is_phishing_predicted": False, "confidence_score": 0.2},
                            "identity_conflict_assessment": {"brand_domain_mismatch_detected": False},
                        },
                    },
                },
            },
        ]

        gt_map = {"obs_001": True, "obs_002": False}
        mm = compute_multimodal_metrics(sample_reports, gt_map)
        self.assertEqual(mm.total_observations, 2)
        self.assertEqual(mm.modality_coverage["url"], 1.0)
        self.assertEqual(mm.modality_coverage["html_nlp"], 0.5)
        self.assertEqual(mm.identity_conflict_rate, 0.5)

    def test_graph_metrics(self):
        reports = [
            {
                "related_observations": [{"id": "obs_2"}, {"id": "obs_3"}],
                "graph_intelligence": {"community": {"cluster_id": "comm_1"}, "temporal_analysis": {"time_bucket": "w1"}},
            },
            {
                "related_observations": [],
                "graph_intelligence": {},
            },
        ]
        g = compute_graph_metrics(reports)
        self.assertEqual(g["total_reports"], 2)
        self.assertEqual(g["total_related_matches"], 2)
        self.assertEqual(g["average_related_matches"], 1.0)
        self.assertEqual(g["reports_with_graph_matches_rate"], 0.5)
        self.assertEqual(g["community_clustering_rate"], 0.5)
        self.assertEqual(g["temporal_burst_rate"], 0.5)

    def test_evaluator_report_generation(self):
        evaluator = MultimodalEvaluator(platform_version="1.0.0")
        sample_reports = [
            {
                "observation_id": "obs_test",
                "runtime_ms": 150.0,
                "module_results": {
                    "url": {"status": "success", "model": {"latency_ms": 12.0}},
                    "html_nlp": {"status": "success", "model": {"latency_ms": 35.0}},
                    "multimodal_fusion": {
                        "status": "success",
                        "model": {"latency_ms": 8.0},
                        "result": {
                            "classification": {"is_phishing_predicted": True, "confidence_score": 0.96},
                            "identity_conflict_assessment": {"brand_domain_mismatch_detected": True},
                        },
                    },
                },
            }
        ]

        gt_map = {"obs_test": True}
        res = evaluator.evaluate(sample_reports, ground_truth_map=gt_map)
        self.assertEqual(res["evaluation_metadata"]["total_investigations_analyzed"], 1)
        self.assertIn("multimodal_fusion", res["classification_benchmarks"])

        md = evaluator.generate_markdown_report(res)
        self.assertIn("# 🛡️ CYRAXI Multimodal Intelligence Platform", md)
        self.assertIn("Modality", md)
        self.assertIn("Throughput", md)


if __name__ == "__main__":
    unittest.main()

