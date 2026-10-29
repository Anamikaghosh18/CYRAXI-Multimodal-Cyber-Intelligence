"""
Tests for the Graph Enrichment Mapper module.
Uses a mock Neo4j driver so tests run without a live database.
"""

import unittest
from unittest.mock import MagicMock, patch

from modules.graph_enrichment_mapper.domain.schemas import GraphIngestRequest
from modules.graph_enrichment_mapper.mapper import GraphEnrichmentMapper, _sha256, _slug


class MockNeo4jDriver:
    """Minimal mock driver that records Cypher calls without hitting Neo4j."""

    def __init__(self):
        self.write_calls = []
        self.query_calls = []

    def run_write(self, cypher, params=None):
        self.write_calls.append((cypher.strip(), params or {}))

    def run_query(self, cypher, params=None):
        self.query_calls.append((cypher.strip(), params or {}))
        return []

    def apply_schema_constraints(self):
        pass


SAMPLE_META = {
    "observation_id": "obs_aabbccddeeff00112233445566778899",
    "url": "http://fake-paypal.xyz/login/verify",
    "brand": "PayPal",
    "sector": "Finance",
    "ip": "1.2.3.4",
    "asn": "AS12345",
    "asn_name": "FakeHosting LLC",
    "host": "fake-paypal.xyz",
    "tld": "xyz",
    "country_code": "RU",
    "country_name": "Russia",
    "family_id": "abc123campaign",
    "isotime": "2020-04-15T12:00:00Z",
    "dataset_id": "phishpedia_primary",
    "source_record_id": "PayPal+2020-04-15-12`00`00",
    "html_hash": "abc123def456",
    "screenshot_hash": "xyz789uvw012",
}

SAMPLE_URL_ENVELOPE = {
    "schema_version": "1.0.0",
    "observation_id": "obs_aabbccddeeff00112233445566778899",
    "run_id": "test_run_001",
    "model": {
        "name": "url_hist_gradient_boosting_calibrated",
        "version": "2.0.0",
        "modality": "url",
        "execution_hardware": "cpu",
        "latency_ms": 1.5,
    },
    "status": "success",
    "result": {
        "classification": {
            "is_phishing_predicted": True,
            "confidence_score": 0.97,
            "verdict": "phishing",
            "top_risk_factors": [
                "Targeted brand name used in URL path (spoofing)",
                "High-abuse top-level domain",
                "Abnormally long URL",
            ],
        }
    },
    "warnings": [],
}


class TestHelpers(unittest.TestCase):
    def test_sha256_deterministic(self):
        h1 = _sha256("paypal")
        h2 = _sha256("paypal")
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)

    def test_slug_normalises(self):
        self.assertEqual(_slug("PayPal Inc."), "paypal_inc_")
        self.assertEqual(_slug("1&1 Ionos"), "1&1_ionos")


class TestGraphEnrichmentMapper(unittest.TestCase):

    def setUp(self):
        self.driver = MockNeo4jDriver()
        self.mapper = GraphEnrichmentMapper(self.driver)

    def _make_request(self, outputs=None):
        return GraphIngestRequest(
            observation_meta=SAMPLE_META,
            model_outputs=outputs or [],
            run_id="test_run_001",
        )

    def test_ingest_without_outputs_creates_core_nodes(self):
        req = self._make_request(outputs=[])
        result = self.mapper.ingest(req)
        self.assertEqual(result.observation_id, SAMPLE_META["observation_id"])
        # Should create: Observation, URL, Domain, IP, AS, Brand, WebPageCapture, Campaign = 8 nodes
        self.assertEqual(result.nodes_merged, 8)

    def test_ingest_creates_expected_node_count_with_url_output(self):
        req = self._make_request(outputs=[SAMPLE_URL_ENVELOPE])
        result = self.mapper.ingest(req)
        # 8 core + 2 (ModelRun + Prediction) + 5 (EvidenceItems: 3 risk factors + confidence + verdict) = 15
        self.assertEqual(result.nodes_merged, 15)

    def test_observation_id_preserved_from_meta(self):
        req = self._make_request()
        result = self.mapper.ingest(req)
        self.assertEqual(result.observation_id, "obs_aabbccddeeff00112233445566778899")

    def test_derived_obs_id_when_not_in_meta(self):
        meta = dict(SAMPLE_META)
        del meta["observation_id"]
        req = GraphIngestRequest(observation_meta=meta, model_outputs=[], run_id="r1")
        result = self.mapper.ingest(req)
        self.assertTrue(result.observation_id.startswith("obs_"))

    def test_no_model_outputs_no_warnings(self):
        req = self._make_request(outputs=[])
        result = self.mapper.ingest(req)
        self.assertEqual(result.warnings, [])

    def test_envelope_without_classification_raises_warning(self):
        bad_envelope = {
            "observation_id": SAMPLE_META["observation_id"],
            "run_id": "r1",
            "model": {"name": "ocr_stub", "version": "1.0", "modality": "ocr", "latency_ms": 0},
            "status": "success",
            "result": {},  # no classification
        }
        req = self._make_request(outputs=[bad_envelope])
        result = self.mapper.ingest(req)
        self.assertTrue(any("skipped" in w for w in result.warnings))

    def test_write_calls_contain_merge_statements(self):
        req = self._make_request(outputs=[])
        self.mapper.ingest(req)
        all_cypher = " ".join(c for c, _ in self.driver.write_calls)
        self.assertIn("MERGE", all_cypher)
        self.assertIn("Observation", all_cypher)
        self.assertIn("Brand", all_cypher)
        self.assertIn("IPAddress", all_cypher)
        self.assertIn("WebPageCapture", all_cypher)

    def test_webpage_capture_node_created_with_hashes(self):
        req = self._make_request(outputs=[])
        self.mapper.ingest(req)
        all_cypher = " ".join(c for c, _ in self.driver.write_calls)
        self.assertIn("WebPageCapture", all_cypher)
        self.assertIn("STORED_AS", all_cypher)
        self.assertIn("html_hash", all_cypher)
        self.assertIn("screenshot_hash", all_cypher)

    def test_evidence_items_created_from_model_output(self):
        req = self._make_request(outputs=[SAMPLE_URL_ENVELOPE])
        result = self.mapper.ingest(req)
        # Should have evidence items from risk factors and other extracted features
        all_cypher = " ".join(c for c, _ in self.driver.write_calls)
        self.assertIn("EvidenceItem", all_cypher)
        self.assertIn("SUPPORTED_BY", all_cypher)
        self.assertIn("metric_name", all_cypher)


if __name__ == "__main__":
    unittest.main()
