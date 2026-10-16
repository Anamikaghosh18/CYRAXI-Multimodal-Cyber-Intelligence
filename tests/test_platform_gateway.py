"""
Tests for Threat Graph Analytics Algorithms and Platform Gateway Service.
All tests run with mock Neo4j driver and mock/live URL service (no database required).
"""

import unittest
from unittest.mock import MagicMock

from modules.graph_enrichment_mapper.algorithms import ThreatGraphAnalyticsEngine
from modules.platform_gateway.service import PlatformGatewayService
from modules.platform_gateway.schemas import URLScanRequest


class MockDriverForAlgorithms:
    """Mock Neo4j driver returning tailored responses for algorithm methods."""

    def __init__(self):
        self.cypher_calls = []

    def run_query(self, cypher: str, params: dict = None):
        self.cypher_calls.append((cypher.strip(), params or {}))
        # 1. Subgraph mock
        if "collect(DISTINCT node)" in cypher:
            return [{
                "raw_nodes": [
                    {"observation_id": "obs_123", "_labels": ["Observation"]},
                    {"raw_url": "http://evil.com/login", "_labels": ["URL"]},
                    {"name": "evil.com", "_labels": ["Domain"]},
                    {"ip": "1.2.3.4", "_labels": ["IPAddress"]},
                ],
                "raw_rels": [
                    {"type": "CAPTURED_URL", "start_node": "obs_123", "end_node": "http://evil.com/login"},
                    {"type": "HOSTED_ON", "start_node": "http://evil.com/login", "end_node": "evil.com"},
                ]
            }]
        # 2. Reputation query (domain/ip/asn)
        if "phish_count" in cypher:
            return [{"phish_count": 8, "brands_count": 3}]
        # 3. Campaign clusters query
        if "CampaignCandidate" in cypher:
            return [{
                "family_id": "kit_alpha_99",
                "campaign_id": "camp_abc",
                "total_observations": 12,
                "targeted_brands": ["PayPal", "Microsoft"],
                "sample_domains": ["pay-login.xyz", "ms-verify.com"],
                "sample_ips": ["1.2.3.4"],
                "hosting_asns": ["BadHost AS"],
            }]
        # 4. Analytics overview
        if "obs_count" in cypher:
            return [{"obs_count": 500, "dom_count": 320, "ip_count": 140, "brand_count": 45}]
        if "TARGETS_BRAND" in cypher:
            return [{"brand": "PayPal", "sector": "Finance", "count": 120}]
        if "ANNOUNCED_BY" in cypher:
            return [{"asn_name": "Cloudflare Inc.", "asn_code": "AS13335", "domain_count": 80}]
        if "country_code" in cypher:
            return [{"code": "US", "name": "United States", "count": 210}]

        return []

    def run_write(self, cypher: str, params: dict = None):
        pass

    def apply_schema_constraints(self):
        pass


class TestGraphAlgorithms(unittest.TestCase):

    def setUp(self):
        self.driver = MockDriverForAlgorithms()
        self.engine = ThreatGraphAnalyticsEngine(self.driver)

    def test_visual_subgraph_generation(self):
        subgraph = self.engine.get_observation_subgraph("obs_123", depth=2)
        self.assertEqual(subgraph["observation_id"], "obs_123")
        self.assertEqual(subgraph["node_count"], 4)
        self.assertEqual(subgraph["edge_count"], 2)

        # Verify styling metadata is present for the UI canvas
        obs_node = next(n for n in subgraph["nodes"] if n["id"] == "obs_123")
        self.assertIn("color", obs_node["style"])
        self.assertIn("shape", obs_node["style"])

    def test_reputation_scoring_high_risk(self):
        rep = self.engine.compute_infrastructure_reputation(
            domain="evil.com",
            ip="1.2.3.4",
            asn="AS999"
        )
        self.assertGreater(rep["graph_risk_score"], 0.70)
        self.assertEqual(rep["verdict"], "malicious")
        self.assertTrue(len(rep["signals"]) >= 2)

    def test_campaign_cluster_discovery(self):
        clusters = self.engine.discover_campaign_clusters(min_size=2)
        self.assertEqual(len(clusters), 1)
        self.assertEqual(clusters[0]["family_id"], "kit_alpha_99")
        self.assertIn("PayPal", clusters[0]["targeted_brands"])
        self.assertIn("Microsoft", clusters[0]["targeted_brands"])

    def test_dashboard_analytics_overview(self):
        overview = self.engine.get_dashboard_analytics_overview()
        self.assertIn("summary", overview)
        self.assertEqual(overview["summary"]["obs_count"], 500)
        self.assertEqual(len(overview["top_targeted_brands"]), 1)
        self.assertEqual(overview["top_targeted_brands"][0]["brand"], "PayPal")


class TestPlatformGatewayService(unittest.TestCase):

    def setUp(self):
        self.driver = MockDriverForAlgorithms()
        self.gateway = PlatformGatewayService(neo4j_driver=self.driver)

    def test_scan_url_produces_complete_platform_response(self):
        req = URLScanRequest(
            url="http://paypal-verification-account-update.xyz/login",
            include_subgraph=True,
            auto_ingest_graph=True,
        )
        res = self.gateway.scan_url(req)

        # Check required fields
        self.assertTrue(res.observation_id.startswith("obs_"))
        self.assertEqual(res.target_url, req.url)
        self.assertGreater(res.latency_ms, 0.0)

        # Check Triage verdict
        self.assertIn(res.triage.verdict, ["phishing", "suspicious", "benign"])
        self.assertIsInstance(res.triage.confidence_score, float)
        self.assertIsInstance(res.triage.fused_risk_score, float)
        self.assertTrue(len(res.triage.top_risk_factors) > 0)

        # Check Visual Subgraph
        self.assertIsNotNone(res.visual_graph)
        self.assertEqual(res.visual_graph.node_count, 4)
        self.assertEqual(res.visual_graph.edge_count, 2)


if __name__ == "__main__":
    unittest.main()
