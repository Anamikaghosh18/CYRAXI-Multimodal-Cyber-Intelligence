"""
Tests for Runtime JSON Schema Validation Service
"""

import unittest
from schemas.validator import (
    validate_model_output,
    validate_observation,
    validate_investigation_report,
)


class TestSchemaValidator(unittest.TestCase):

    def test_valid_model_output(self):
        valid_envelope = {
            "schema_version": "1.0.0",
            "observation_id": "obs_1234567890abcdef1234567890abcdef",
            "run_id": "run_test_001",
            "model": {
                "name": "url_feature_classifier",
                "version": "1.0.0",
                "modality": "url",
            },
            "status": "success",
            "created_at": "2026-11-05T12:00:00Z",
            "result": {
                "classification": {
                    "is_phishing_predicted": True,
                    "confidence_score": 0.95,
                    "verdict": "phishing",
                }
            },
            "warnings": [],
        }
        is_valid, errors = validate_model_output(valid_envelope)
        self.assertTrue(is_valid, f"Validation errors: {errors}")

    def test_invalid_model_output_missing_fields(self):
        invalid_envelope = {
            "schema_version": "1.0.0",
            # missing observation_id, run_id, etc.
        }
        is_valid, errors = validate_model_output(invalid_envelope)
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)


if __name__ == "__main__":
    unittest.main()
