
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

from modules.dataset_adapter.reader import PhishpediaDatasetReader
from modules.dataset_adapter.artifacts import read_artifact_bytes
from modules.ocr_extractor.extractor import extract_ocr


class TestOCRZipIntegration(unittest.TestCase):

    def test_screenshot_is_read_from_zip_and_processed(self):
        with tempfile.TemporaryDirectory() as temp:
            archive_path = Path(temp) / "ocr_test.zip"

            # Create a synthetic screenshot with readable text.
            image = Image.new("RGB", (800, 250), "white")
            draw = ImageDraw.Draw(image)
            draw.text((40, 60), "LOGIN TO YOUR ACCOUNT", fill="black")
            draw.text((40, 120), "PASSWORD", fill="black")

            image_buffer = io.BytesIO()
            image.save(image_buffer, format="PNG")
            screenshot_bytes = image_buffer.getvalue()

            # The reader expects Phishpedia-style record files.
            info = {
                "url": "https://example.com/login",
                "brand": "Example",
            }

            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr(
                    "record_a/info.txt",
                    repr(info),
                )
                archive.writestr(
                    "record_a/shot.png",
                    screenshot_bytes,
                )
                archive.writestr(
                    "record_a/html.txt",
                    "<html><title>Login</title></html>",
                )

            reader = PhishpediaDatasetReader(str(archive_path))
            observations = list(
                reader.stream_observations(limit=1)
            )

            self.assertEqual(len(observations), 1)
            observation = observations[0]

            # Verify that the adapter resolves and reads the screenshot.
            image_bytes = read_artifact_bytes(
                archive_path,
                observation,
                "screenshot",
            )
            self.assertIsNotNone(image_bytes)
            self.assertEqual(image_bytes, screenshot_bytes)

            # Verify that the OCR engine processes the ZIP artifact.
            fake_data = {
                "text": ["LOGIN", "PASSWORD"],
                "left": [40, 40],
                "top": [60, 120],
                "width": [45, 80],
                "height": [12, 12],
                "conf": [95, 98],
            }
            with patch(
                "modules.ocr_extractor.extractor.pytesseract.image_to_data",
                return_value=fake_data,
            ):
                result = extract_ocr(
                    observation_id=observation["observation_id"],
                    run_id="ocr-zip-integration-test",
                    screenshot_bytes=image_bytes,
                )

            self.assertEqual(result["status"], "success")
            self.assertEqual(
                result["result"]["source"],
                "screenshot_ocr",
            )
            self.assertGreater(
                result["result"]["text_character_count"], 0
            )

            text = result["result"]["extracted_text_raw"].lower()
            self.assertIn("password", text)

            # Check that the output can be serialized as JSON.
            json.dumps(result, ensure_ascii=False)


if __name__ == "__main__":
    unittest.main()
