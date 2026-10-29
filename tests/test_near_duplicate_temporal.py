"""
Tests for Near-Duplicate and Temporal Analysis
"""

import unittest
from modules.graph_ai.near_duplicate.detector import NearDuplicateDetector
from modules.graph_ai.temporal.analyzer import TemporalGraphAnalyzer


class TestNearDuplicateDetector(unittest.TestCase):
    def setUp(self):
        self.detector = NearDuplicateDetector(threshold=0.7)

    def test_normalize_html(self):
        html = "<script>alert('test')</script><div>Hello World</div>"
        normalized = self.detector._normalize_html(html)
        self.assertNotIn("script", normalized)
        self.assertIn("hello world", normalized)

    def test_add_and_query_html(self):
        html1 = "<div>This is a longer piece of content that should generate enough shingles for testing</div>" * 5
        html2 = "<div>This is a longer piece of content that should generate enough shingles for testing</div>" * 5
        html3 = "<div>This is completely different content that should not match the other documents</div>" * 5

        self.detector.add_html("obs_1", html1)
        self.detector.add_html("obs_2", html2)
        self.detector.add_html("obs_3", html3)

        duplicates = self.detector.query_duplicates("obs_1")
        self.assertGreater(len(duplicates), 0)
        self.assertIn("obs_2", [d[0] for d in duplicates])

    def test_statistics(self):
        html = "<div>This is a longer piece of content that should generate enough shingles for testing</div>" * 5
        self.detector.add_html("obs_1", html)
        stats = self.detector.get_statistics()
        self.assertEqual(stats["processed_documents"], 1)


class TestTemporalGraphAnalyzer(unittest.TestCase):
    def setUp(self):
        self.analyzer = TemporalGraphAnalyzer()

    def test_add_observation(self):
        self.analyzer.add_observation("obs_1", "2019-07-01T00:00:00Z")
        self.analyzer.add_observation("obs_2", "2019-07-08T00:00:00Z")

        stats = self.analyzer.get_statistics()
        self.assertEqual(stats["total_observations"], 2)

    def test_build_time_windowed_graph(self):
        self.analyzer.add_observation("obs_1", "2019-07-01T00:00:00Z")
        self.analyzer.add_observation("obs_2", "2019-07-05T00:00:00Z")
        self.analyzer.add_observation("obs_3", "2019-07-10T00:00:00Z")

        graph = self.analyzer.build_time_windowed_graph(window_days=7)
        self.assertGreater(graph.number_of_edges(), 0)

    def test_detect_bursts(self):
        for i in range(10):
            self.analyzer.add_observation(f"obs_{i}", f"2019-07-01T00:00:00Z")

        bursts = self.analyzer.detect_bursts(window_days=7, min_observations=5)
        self.assertGreater(len(bursts), 0)


if __name__ == "__main__":
    unittest.main()
