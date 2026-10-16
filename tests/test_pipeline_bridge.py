"""
Tests for the run_pipeline bridge (dry-run mode — no Neo4j or zip needed).
Uses mocks for the dataset reader, URL service, and mapper.
"""

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# We import the core function, not __main__ behaviour
from run_pipeline import _build_graph_meta, run_pipeline


# ── Sample canonical observation (matches reader output shape) ─────────────
SAMPLE_OBS = {
    "observation_id": "obs_aabbccddeeff00112233445566778899",
    "source_record_id": "PayPal+2020-04-15-12`00`00",
    "dataset": {"dataset_id": "phishpedia_primary"},
    "url": {
        "raw": "http://fake-paypal.xyz/login/verify",
        "host": "fake-paypal.xyz",
        "tld": "xyz",
    },
    "network": {
        "ip": "1.2.3.4",
        "asn": "AS999",
        "asn_name": "BadHost LLC",
        "country_code": "RU",
        "country_name": "Russia",
    },
    "label": {
        "ground_truth": {
            "target_brand": "PayPal",
            "target_sector": "Finance",
        }
    },
    "source": {"family_id": "abc123campaign"},
    "timestamps": {"captured_at": "2020-04-15T12:00:00Z"},
}


class TestBuildGraphMeta(unittest.TestCase):
    def test_all_expected_keys_present(self):
        meta = _build_graph_meta(SAMPLE_OBS)
        for key in ["observation_id", "url", "brand", "ip", "asn", "family_id", "host"]:
            self.assertIn(key, meta, f"Expected key '{key}' missing from graph meta")

    def test_values_extracted_correctly(self):
        meta = _build_graph_meta(SAMPLE_OBS)
        self.assertEqual(meta["observation_id"], "obs_aabbccddeeff00112233445566778899")
        self.assertEqual(meta["url"], "http://fake-paypal.xyz/login/verify")
        self.assertEqual(meta["brand"], "PayPal")
        self.assertEqual(meta["ip"], "1.2.3.4")
        self.assertEqual(meta["family_id"], "abc123campaign")

    def test_missing_fields_default_to_empty_string(self):
        meta = _build_graph_meta({})  # completely empty observation
        self.assertEqual(meta.get("url", ""), "")
        self.assertEqual(meta.get("brand", ""), "")


class TestRunPipelineDryRun(unittest.TestCase):
    """
    Exercises run_pipeline() with dry_run=True and mocked reader/service.
    No zip file or Neo4j connection required.
    """

    def _make_mock_envelope(self):
        env = MagicMock()
        env.model_dump.return_value = {
            "observation_id": SAMPLE_OBS["observation_id"],
            "run_id": "test_run",
            "model": {"name": "hgb", "version": "2.0", "modality": "url", "latency_ms": 1.0},
            "status": "success",
            "result": {
                "classification": {
                    "verdict": "phishing",
                    "confidence_score": 0.95,
                    "is_phishing_predicted": True,
                    "top_risk_factors": ["brand_in_path"],
                }
            },
            "warnings": [],
        }
        return env

    @patch("run_pipeline.PhishpediaDatasetReader")
    @patch("run_pipeline.load_url_service")
    def test_dry_run_processes_records(self, mock_load_service, mock_reader_cls):
        # Setup mocks
        mock_reader = MagicMock()
        mock_reader.stream_observations.return_value = iter([SAMPLE_OBS, SAMPLE_OBS])
        mock_reader_cls.return_value = mock_reader

        mock_service = MagicMock()
        mock_service.analyze.return_value = self._make_mock_envelope()
        mock_load_service.return_value = mock_service

        summary = run_pipeline(
            limit=2,
            dry_run=True,
            archive_path="data/fake.zip",
            verbose=False,
        )

        self.assertEqual(summary["total_processed"], 2)
        self.assertEqual(summary["total_phishing"], 2)
        self.assertEqual(summary["total_nodes"], 0)   # dry_run = no DB writes
        self.assertEqual(summary["error_count"], 0)
        self.assertTrue(Path(summary["log_path"]).exists())

    @patch("run_pipeline.PhishpediaDatasetReader")
    @patch("run_pipeline.load_url_service")
    def test_log_file_contains_jsonl_records(self, mock_load_service, mock_reader_cls):
        mock_reader = MagicMock()
        mock_reader.stream_observations.return_value = iter([SAMPLE_OBS])
        mock_reader_cls.return_value = mock_reader

        mock_service = MagicMock()
        mock_service.analyze.return_value = self._make_mock_envelope()
        mock_load_service.return_value = mock_service

        summary = run_pipeline(
            limit=1, dry_run=True,
            archive_path="data/fake.zip", verbose=False,
        )

        log_path = Path(summary["log_path"])
        lines = log_path.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 1)
        record = json.loads(lines[0])
        self.assertIn("verdict", record)
        self.assertIn("confidence", record)


if __name__ == "__main__":
    unittest.main()
