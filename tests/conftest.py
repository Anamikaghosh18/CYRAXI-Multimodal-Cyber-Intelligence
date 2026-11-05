"""
Global Pytest Fixtures for CYRAXI Test Suite
Provides standard test doubles, mock drivers, and canonical observation fixtures.
"""

import pytest
from typing import Any, Dict, List


class MockNeo4jDriver:
    """Standard mock Neo4j driver for unit tests without a live database."""

    def __init__(self):
        self.write_calls: List[tuple] = []
        self.query_calls: List[tuple] = []
        self._connected = True

    def connect(self) -> None:
        self._connected = True

    def run_write(self, cypher: str, params: Dict[str, Any] = None) -> None:
        self.write_calls.append((cypher.strip(), params or {}))

    def run_query(self, cypher: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        self.query_calls.append((cypher.strip(), params or {}))
        return []

    def run_read(self, cypher: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        return self.run_query(cypher, params)

    def apply_schema_constraints(self) -> None:
        pass

    def close(self) -> None:
        self._connected = False


@pytest.fixture
def mock_neo4j():
    """Provides a fresh MockNeo4jDriver instance."""
    return MockNeo4jDriver()


@pytest.fixture
def sample_canonical_observation() -> Dict[str, Any]:
    """Provides a canonical Observation dict matching schemas/observation.schema.json."""
    return {
        "schema_version": "1.0.0",
        "observation_id": "obs_aabbccddeeff00112233445566778899",
        "dataset": {
            "dataset_id": "phishpedia_primary",
            "version": "1.0.0",
            "split": "test",
        },
        "source_record_id": "PayPal+2020-04-15-12`00`00",
        "url": {
            "raw": "http://fake-paypal.xyz/login/verify",
            "scheme": "http",
            "host": "fake-paypal.xyz",
            "domain": "fake-paypal.xyz",
            "subdomain": None,
            "tld": "xyz",
            "port": 80,
            "path": "/login/verify",
            "query": "",
            "fragment": "",
        },
        "timestamps": {
            "captured_at": "2020-04-15T12:00:00Z",
            "ingested_at": "2026-11-05T12:00:00Z",
        },
        "label": {
            "ground_truth": {
                "verdict": "phishing",
                "target_brand": "PayPal",
                "target_sector": "Finance",
            }
        },
        "network": {
            "ip": "1.2.3.4",
            "asn": "AS12345",
            "asn_name": "FakeHosting LLC",
            "country_code": "RU",
            "country_name": "Russia",
        },
        "source": {
            "family_id": "campaign_alpha",
        },
        "artifacts": {
            "screenshot": {"relative_path": "record_a/shot.png", "storage_medium": "zip_entry"},
            "html": {"relative_path": "record_a/html.txt", "storage_medium": "zip_entry"},
        },
        "availability": {
            "has_screenshot": True,
            "has_html": True,
            "has_ocr": False,
        },
    }


@pytest.fixture
def sample_graph_meta() -> Dict[str, Any]:
    """Provides a flat metadata dict for GraphEnrichmentMapper ingestion."""
    return {
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
        "family_id": "campaign_alpha",
        "isotime": "2020-04-15T12:00:00Z",
        "dataset_id": "phishpedia_primary",
        "source_record_id": "PayPal+2020-04-15-12`00`00",
    }


@pytest.fixture
def sample_model_output_envelope() -> Dict[str, Any]:
    """Provides a canonical ModelOutputEnvelope matching schemas/model-output.schema.json."""
    return {
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
        "created_at": "2026-11-05T12:00:00Z",
        "result": {
            "classification": {
                "is_phishing_predicted": True,
                "confidence_score": 0.97,
                "verdict": "phishing",
                "top_risk_factors": [
                    "Targeted brand name used in URL path (spoofing)",
                    "High-abuse top-level domain",
                ],
            }
        },
        "warnings": [],
        "error_details": None,
    }
