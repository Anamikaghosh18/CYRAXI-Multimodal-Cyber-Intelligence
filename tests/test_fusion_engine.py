import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from modules.fusion_engine.fusion import fuse_predictions


OBS_ID = "obs_0123456789abcdef0123456789abcdef"
RUN_ID = "run_test_123"


def envelope(modality, *, status="success", score=None, predicted=None, result=None,
             observation_id=OBS_ID, run_id=RUN_ID):
    payload = result or {}
    if score is not None:
        payload["classification"] = {
            "confidence_score": score,
            "is_phishing_predicted": predicted,
        }
    return {
        "schema_version": "1.0.0",
        "observation_id": observation_id,
        "run_id": run_id,
        "model": {"name": modality, "version": "1", "modality": modality},
        "status": status,
        "result": payload,
        "warnings": [],
        "error_details": None,
    }


class TestFusionEngine(unittest.TestCase):
    def test_renormalizes_only_compatible_url_and_html_probabilities(self):
        outputs = [
            envelope("url", score=0.8, predicted=True),
            envelope("html_nlp", score=0.4, predicted=False),
            envelope("ocr", result={
                "text_character_count": 20,
                "extracted_credentials_keywords": ["password"],
                "classification": {"confidence_score": 0.99},
            }),
            envelope("computer_vision", result={
                "detected_elements": [{}, {}],
                "brand_match_performed": False,
            }),
        ]
        result = fuse_predictions(OBS_ID, RUN_ID, outputs)
        self.assertEqual(result["status"], "success")
        self.assertAlmostEqual(
            result["result"]["classification"]["confidence_score"], 0.6182
        )
        self.assertEqual(result["result"]["active_modalities"], ["url", "html_nlp"])
        self.assertEqual(
            [item["score"] for item in result["result"]["evidence_summary"]],
            [0.8, 0.4, None, None],
        )
        self.assertIn("uncalibrated", " ".join(result["result"]["limitations"]))

    def test_one_valid_probability_is_renormalized_to_full_active_weight(self):
        outputs = [
            envelope("url", score=0.73, predicted=True),
            envelope("html_nlp", status="skipped"),
            envelope("ocr", status="skipped"),
            envelope("computer_vision", status="skipped"),
        ]
        result = fuse_predictions(OBS_ID, RUN_ID, outputs)
        self.assertEqual(result["result"]["classification"]["confidence_score"], 0.73)
        self.assertEqual(result["result"]["active_modalities"], ["url"])
        self.assertEqual(result["status"], "partial")

    def test_ocr_cv_evidence_without_probabilities_has_no_verdict(self):
        outputs = [
            envelope("url", status="skipped"),
            envelope("html_nlp", status="skipped"),
            envelope("ocr", result={
                "text_character_count": 12,
                "extracted_credentials_keywords": ["login"],
            }),
            envelope("computer_vision", result={
                "detected_elements": [{}],
                "brand_match_performed": False,
            }),
        ]
        result = fuse_predictions(OBS_ID, RUN_ID, outputs)
        self.assertEqual(result["status"], "partial")
        self.assertTrue(result["result"]["insufficient_evidence"])
        self.assertNotIn("classification", result["result"])
        self.assertEqual(result["result"]["supporting_evidence"], [])

    def test_mismatched_observation_output_is_ignored(self):
        outputs = [
            envelope("url", score=0.9, predicted=True,
                     observation_id="obs_ffffffffffffffffffffffffffffffff"),
            envelope("ocr", result={"text_character_count": 0}),
        ]
        result = fuse_predictions(OBS_ID, RUN_ID, outputs)
        codes = [warning["code"] for warning in result["warnings"]]
        self.assertIn("W_OBSERVATION_ID_MISMATCH", codes)
        self.assertNotIn("classification", result["result"])

    def test_duplicate_modality_is_not_double_counted(self):
        outputs = [
            envelope("url", score=0.8, predicted=True),
            envelope("url", score=0.2, predicted=False),
            envelope("html_nlp", status="skipped"),
            envelope("ocr", status="skipped"),
            envelope("computer_vision", status="skipped"),
        ]
        result = fuse_predictions(OBS_ID, RUN_ID, outputs)
        self.assertEqual(result["result"]["classification"]["confidence_score"], 0.8)
        self.assertIn(
            "W_DUPLICATE_MODALITY_OUTPUT",
            [warning["code"] for warning in result["warnings"]],
        )

    def test_invalid_weight_configuration_returns_clear_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config = Path(temp_dir) / "fusion_weights.yaml"
            config.write_text(
                "weights:\n"
                "  url: -0.1\n"
                "  html_nlp: 0.25\n"
                "  ocr: 0.1\n"
                "  computer_vision: 0.35\n",
                encoding="utf-8",
            )
            with patch("modules.fusion_engine.fusion.CONFIG_PATH", config):
                result = fuse_predictions(OBS_ID, RUN_ID, [])
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["warnings"][0]["code"], "W_FUSION_CONFIG_INVALID")
        self.assertIn("non-negative", result["error_details"]["message"])

    def test_invalid_probability_is_rejected(self):
        outputs = [
            envelope("url", score=float("nan"), predicted=True),
            envelope("ocr", result={"text_character_count": 2}),
        ]
        result = fuse_predictions(OBS_ID, RUN_ID, outputs)
        self.assertTrue(result["result"]["insufficient_evidence"])
        self.assertIn(
            "W_INVALID_MODALITY_SCORE",
            [warning["code"] for warning in result["warnings"]],
        )


if __name__ == "__main__":
    unittest.main()
