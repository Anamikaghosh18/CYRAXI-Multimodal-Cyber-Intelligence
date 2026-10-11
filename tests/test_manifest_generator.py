import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.manifest_generator import generate_manifest


SAMPLE_OBSERVATION = {
    "schema_version": "1.0.0",
    "observation_id": "obs_1234567890abcdef1234567890abcdef",
    "source_record_id": "sample_record",
    "url": {"raw": "https://example.com/login"},
    "label": {
        "ground_truth": {"normalized_label": "phishing"}
    },
    "availability": {
        "has_screenshot": True,
        "has_html": True,
        "has_ocr": False,
    },
}


class TestManifestGenerator(unittest.TestCase):

    def test_writes_jsonl_and_csv(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "manifest"

            # Patch the actual class used by the generator.
            with patch(
                "scripts.manifest_generator.PhishpediaDatasetReader"
            ) as reader_class:
                reader_class.return_value.stream_observations.return_value = [
                    SAMPLE_OBSERVATION
                ]

                count, jsonl_path, csv_path = generate_manifest(
                    "fake.zip", output_dir, limit=1
                )

            self.assertEqual(count, 1)
            self.assertTrue(jsonl_path.exists())
            self.assertTrue(csv_path.exists())

            with jsonl_path.open(encoding="utf-8") as file:
                record = json.loads(file.readline())

            self.assertEqual(
                record["observation_id"],
                SAMPLE_OBSERVATION["observation_id"],
            )

            with csv_path.open(
                encoding="utf-8", newline=""
            ) as file:
                rows = list(csv.DictReader(file))

            self.assertEqual(len(rows), 1)
            self.assertEqual(
                rows[0]["url"], "https://example.com/login"
            )
            self.assertEqual(rows[0]["has_html"], "True")
            self.assertEqual(rows[0]["has_ocr"], "False")

    def test_empty_dataset_writes_csv_header(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch(
                "scripts.manifest_generator.PhishpediaDatasetReader"
            ) as reader_class:
                reader_class.return_value.stream_observations.return_value = []

                count, jsonl_path, csv_path = generate_manifest(
                    "fake.zip", temp_dir, limit=1
                )

            self.assertEqual(count, 0)
            self.assertEqual(jsonl_path.read_text(encoding="utf-8"), "")
            with csv_path.open(
                encoding="utf-8", newline=""
            ) as file:
                rows = list(csv.DictReader(file))
            self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
