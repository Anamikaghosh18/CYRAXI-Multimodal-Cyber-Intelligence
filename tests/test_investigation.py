"""
Tests for Investigation Workflow
"""

import unittest
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from modules.investigation.service import InvestigationService
from modules.investigation.persistence import InvestigationPersistence


class TestInvestigationService(unittest.TestCase):
    def setUp(self):
        self.service = InvestigationService(
            archive_path="data/phish_sample_30k.zip",
            neo4j_driver=Mock(),
        )

    def test_validate_observation_id_valid(self):
        self.assertTrue(self.service._validate_observation_id("obs_5defe88b6365fae970616012cf8ef3a2"))

    def test_validate_observation_id_invalid(self):
        self.assertFalse(self.service._validate_observation_id("invalid_id"))
        self.assertFalse(self.service._validate_observation_id("obs_123"))

    def test_validate_url_valid(self):
        self.assertTrue(self.service._validate_url("http://example.com"))
        self.assertTrue(self.service._validate_url("https://example.com/path"))

    def test_validate_url_invalid(self):
        self.assertFalse(self.service._validate_url("not a url"))
        self.assertFalse(self.service._validate_url(""))

    def test_generate_investigation_id(self):
        obs_id = "obs_5defe88b6365fae970616012cf8ef3a2"
        inv_id = self.service._generate_investigation_id(obs_id)
        self.assertTrue(inv_id.startswith("inv_"))
        self.assertEqual(len(inv_id), 36)  # inv_ + 32 hex chars

    def test_generate_similarity_explanation(self):
        features = {"url_similarity": 0.8, "html_similarity": 0.6}
        explanation = self.service._generate_similarity_explanation(features)
        self.assertIn("url_similarity", explanation)
        self.assertIn("html_similarity", explanation)

    def test_generate_similarity_explanation_empty(self):
        explanation = self.service._generate_similarity_explanation({})
        self.assertEqual(explanation, "Similarity based on graph connectivity")

    @patch.object(InvestigationService, '_get_observation_by_id')
    def test_investigate_invalid_observation_id(self, mock_get):
        mock_get.return_value = None
        report = self.service.investigate("invalid_id", input_type="observation_id")
        self.assertEqual(report["status"], "error")
        self.assertTrue(any(w["code"] == "INVALID_OBSERVATION_ID" for w in report["warnings"]))

    @patch.object(InvestigationService, '_get_observation_by_id')
    def test_investigate_observation_not_found(self, mock_get):
        mock_get.return_value = None
        report = self.service.investigate("obs_1234567890abcdef1234567890abcdef", input_type="observation_id")
        self.assertEqual(report["status"], "error")
        self.assertTrue(any(w["code"] == "OBSERVATION_NOT_FOUND" for w in report["warnings"]))


class TestInvestigationPersistence(unittest.TestCase):
    def setUp(self):
        self.output_dir = Path("output/test_investigations")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.persistence = InvestigationPersistence(
            neo4j_driver=None,
            output_dir=str(self.output_dir),
        )

    def tearDown(self):
        # Clean up test files
        import shutil
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)

    def test_persist_to_filesystem(self):
        report = {
            "investigation_id": "inv_test1234567890abcdef1234567890ab",
            "observation_id": "obs_test1234567890abcdef1234567890ab",
            "status": "success",
            "created_at": "2024-01-01T00:00:00Z",
        }

        filepath = self.persistence.persist_to_filesystem(report)

        self.assertTrue(Path(filepath).exists())

        with open(filepath, "r") as f:
            loaded_report = json.load(f)

        self.assertEqual(loaded_report["investigation_id"], report["investigation_id"])

    def test_persist_both_backends(self):
        report = {
            "investigation_id": "inv_test1234567890abcdef1234567890ab",
            "observation_id": "obs_test1234567890abcdef1234567890ab",
            "status": "success",
            "created_at": "2024-01-01T00:00:00Z",
        }

        result = self.persistence.persist(report, neo4j=False, filesystem=True)

        self.assertIsNotNone(result["filesystem"])
        self.assertEqual(result["neo4j"], None)


if __name__ == "__main__":
    unittest.main()
