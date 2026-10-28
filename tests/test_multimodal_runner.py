import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

from modules.dataset_adapter.reader import (
    PhishpediaDatasetReader,
    generate_observation_id,
)
from scripts.run_multimodal import run_pipeline


RUN_ID = "run_integration_001"
ROOT = Path(__file__).resolve().parents[1]


def assert_json_schema_or_required_shape(test_case, instance, schema_filename):
    schema = json.loads(
        (ROOT / "schemas" / schema_filename).read_text(encoding="utf-8")
    )
    try:
        import jsonschema
    except ImportError:
        # No JSON Schema validator is declared or installed in this project
        # environment. Keep basic contract assertions active in that case.
        for field in schema.get("required", []):
            test_case.assertIn(field, instance)
        if schema_filename == "model-output.schema.json":
            for field in schema["properties"]["model"]["required"]:
                test_case.assertIn(field, instance["model"])
            test_case.assertIn(
                instance["status"], schema["properties"]["status"]["enum"]
            )
    else:
        jsonschema.Draft202012Validator(
            schema,
            format_checker=jsonschema.FormatChecker(),
        ).validate(instance)


class TestMultimodalRunner(unittest.TestCase):
    def setUp(self):
        image = Image.new("RGB", (320, 160), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((10, 10, 80, 45), fill="navy")
        draw.text((20, 18), "BRAND", fill="white")
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        self.screenshot = buffer.getvalue()
        self.fake_ocr = {
            "text": ["LOGIN", "PASSWORD"],
            "left": [18, 22],
            "top": [55, 88],
            "width": [48, 72],
            "height": [12, 12],
            "conf": [94, 96],
        }

    def _write_archive(self, path, records):
        with zipfile.ZipFile(path, "w") as archive:
            for name, fields in records.items():
                info = {
                    "url": fields.get("url", "https://example.test/login"),
                    "brand": "Example",
                    "sector": "Online Services",
                    "isotime": "2020-01-02T03:04:05Z",
                }
                archive.writestr(f"{name}/info.txt", repr(info))
                if fields.get("screenshot", True):
                    archive.writestr(f"{name}/shot.png", self.screenshot)
                if fields.get("html", True):
                    archive.writestr(
                        f"{name}/html.txt",
                        "<html><title>Login</title><form action='/login' "
                        "method='post'><input type='password'></form>"
                        "<p>Verify your account immediately</p></html>",
                    )
                if fields.get("ocr", True):
                    archive.writestr(f"{name}/ocr.txt", "Login with password")
                if fields.get("coords", True):
                    archive.writestr(f"{name}/yolo_coords.txt", "10 10 80 45")

    def _run(self, archive_path, output_dir, *, limit, mutate=None):
        original_stream = PhishpediaDatasetReader.stream_observations

        def stream(reader, limit=50, offset=0):
            for observation in original_stream(reader, limit=limit, offset=offset):
                if mutate:
                    mutate(observation)
                yield observation

        with patch.object(PhishpediaDatasetReader, "stream_observations", stream), patch(
            "modules.ocr_extractor.extractor.pytesseract.image_to_data",
            return_value=self.fake_ocr,
        ):
            summary = run_pipeline(
                archive_path,
                output_dir,
                limit=limit,
                run_id=RUN_ID,
            )
        output_path = Path(output_dir) / "model_outputs.jsonl"
        outputs = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
        return summary, outputs

    def test_complete_synthetic_zip_runs_all_modules_and_fusion(self):
        with tempfile.TemporaryDirectory() as temp:
            archive_path = Path(temp) / "complete.zip"
            output_dir = Path(temp) / "out"
            self._write_archive(archive_path, {"record_full": {}})
            summary, outputs = self._run(archive_path, output_dir, limit=1)

            self.assertEqual(summary["counts"]["observations"], 1)
            self.assertEqual(len(outputs), 5)
            observation_id = outputs[0]["observation_id"]
            self.assertTrue(observation_id.startswith("obs_"))
            self.assertEqual({output["observation_id"] for output in outputs}, {observation_id})
            self.assertEqual({output["run_id"] for output in outputs}, {RUN_ID})
            self.assertEqual(
                [output["model"]["modality"] for output in outputs],
                ["url", "html_nlp", "ocr", "computer_vision", "multimodal_fusion"],
            )
            fusion = outputs[-1]
            self.assertEqual(fusion["result"]["active_modalities"], ["url", "html_nlp"])
            summary_by_modality = {
                item["modality"]: item
                for item in fusion["result"]["evidence_summary"]
            }
            self.assertIsNone(summary_by_modality["ocr"]["score"])
            self.assertIsNone(summary_by_modality["computer_vision"]["score"])
            self.assertEqual(
                outputs[3]["result"]["classification"]["num_candidates_found"], 1
            )
            self.assertTrue(all(output["schema_version"] == "1.0.0" for output in outputs))
            for output in outputs:
                assert_json_schema_or_required_shape(
                    self, output, "model-output.schema.json"
                )
            observation = next(
                PhishpediaDatasetReader(str(archive_path)).stream_observations(limit=1)
            )
            assert_json_schema_or_required_shape(
                self, observation, "observation.schema.json"
            )

    def test_missing_artifact_cases_do_not_abort_batch(self):
        with tempfile.TemporaryDirectory() as temp:
            archive_path = Path(temp) / "missing.zip"
            output_dir = Path(temp) / "out"
            records = {
                "record_no_html": {"html": False},
                "record_no_ocr": {"ocr": False},
                "record_no_screenshot": {"screenshot": False},
                "record_no_coords": {"coords": False},
                "record_no_url": {"url": ""},
                "record_minimal": {
                    "html": False, "screenshot": False, "ocr": False,
                    "coords": False, "url": "",
                },
            }
            self._write_archive(archive_path, records)
            summary, outputs = self._run(
                archive_path, output_dir, limit=len(records)
            )
            self.assertEqual(summary["counts"]["observations"], len(records))
            grouped = {}
            for output in outputs:
                grouped.setdefault(output["observation_id"], []).append(output)
            self.assertEqual(len(grouped), len(records))
            for observation_outputs in grouped.values():
                self.assertEqual(len(observation_outputs), 5)
                self.assertEqual(
                    {item["run_id"] for item in observation_outputs}, {RUN_ID}
                )
                self.assertNotIn("error", [item["status"] for item in observation_outputs])

            by_record = {
                name: {
                    item["model"]["modality"]: item
                    for item in grouped[generate_observation_id("phishpedia_primary", name)]
                }
                for name in records
            }
            self.assertEqual(by_record["record_no_html"]["html_nlp"]["status"], "skipped")
            self.assertEqual(by_record["record_no_ocr"]["ocr"]["status"], "success")
            self.assertEqual(by_record["record_no_screenshot"]["computer_vision"]["status"], "skipped")
            self.assertEqual(by_record["record_no_coords"]["computer_vision"]["status"], "skipped")
            no_url = by_record["record_no_url"]["url"]
            self.assertEqual(no_url["status"], "skipped")
            self.assertIn("W_URL_EMPTY", [warning["code"] for warning in no_url["warnings"]])
            self.assertEqual(by_record["record_minimal"]["multimodal_fusion"]["status"], "skipped")

    def test_invalid_manifest_paths_are_treated_as_missing_artifacts(self):
        with tempfile.TemporaryDirectory() as temp:
            archive_path = Path(temp) / "bad_paths.zip"
            output_dir = Path(temp) / "out"
            self._write_archive(archive_path, {"record_bad_paths": {}})

            def break_paths(observation):
                observation["artifacts"]["html"]["relative_path"] = "../outside.html"
                observation["artifacts"]["ocr"]["relative_path"] = "../outside.ocr"
                observation["artifacts"]["screenshot"]["relative_path"] = "../outside.png"
                observation["artifacts"]["auxiliary"]["yolo_coords_path"] = "../outside.txt"

            summary, outputs = self._run(
                archive_path, output_dir, limit=1, mutate=break_paths
            )
            self.assertEqual(summary["counts"]["observations"], 1)
            self.assertEqual(len(outputs), 5)
            self.assertEqual(outputs[1]["status"], "skipped")
            self.assertEqual(outputs[2]["status"], "skipped")
            self.assertEqual(outputs[3]["status"], "skipped")
            self.assertNotIn("error", [output["status"] for output in outputs])


if __name__ == "__main__":
    unittest.main()
