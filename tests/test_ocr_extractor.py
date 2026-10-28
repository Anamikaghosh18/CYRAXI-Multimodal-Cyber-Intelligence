
import io
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

from modules.ocr_extractor.extractor import extract_ocr


class TestOCRExtractor(unittest.TestCase):

    def make_test_screenshot(self):
        """Create a small synthetic screenshot with readable text."""
        image = Image.new("RGB", (800, 250), "white")
        draw = ImageDraw.Draw(image)
        draw.text((40, 60), "LOGIN TO YOUR ACCOUNT", fill="black")
        draw.text((40, 120), "PASSWORD", fill="black")

        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    @staticmethod
    def fake_tesseract_data(*args, **kwargs):
        return {
            "text": ["LOGIN", "TO", "YOUR", "ACCOUNT", "PASSWORD"],
            "left": [40, 100, 130, 180, 40],
            "top": [60, 60, 60, 60, 120],
            "width": [45, 18, 36, 75, 80],
            "height": [12, 12, 12, 12, 12],
            "conf": [95, 96, 94, 93, 98],
        }

    def test_extracts_text_from_screenshot(self):
        with patch(
            "modules.ocr_extractor.extractor.pytesseract.image_to_data",
            side_effect=self.fake_tesseract_data,
        ):
            result = extract_ocr(
                observation_id="test-001",
                run_id="ocr-test-run",
                screenshot_bytes=self.make_test_screenshot(),
            )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["model"]["modality"], "ocr")
        self.assertEqual(
            result["result"]["source"], "screenshot_ocr"
        )
        self.assertGreater(
            result["result"]["text_character_count"], 0
        )
        self.assertIsInstance(
            result["result"]["bounding_boxes"], list
        )
        self.assertEqual(
            result["result"]["text_character_count"],
            len(result["result"]["extracted_text_raw"]),
        )
        self.assertAlmostEqual(result["result"]["confidence_mean"], 0.952)
        for box in result["result"]["bounding_boxes"]:
            self.assertEqual(len(box["box_2d"]), 4)
            self.assertLess(box["box_2d"][0], box["box_2d"][2])
            self.assertLess(box["box_2d"][1], box["box_2d"][3])

        text = result["result"]["extracted_text_raw"].lower()
        self.assertIn("password", text)

    def test_missing_screenshot_and_text_is_skipped(self):
        result = extract_ocr(
            observation_id="test-002",
            run_id="ocr-test-run",
        )

        self.assertEqual(result["status"], "skipped")
        self.assertEqual(
            result["result"]["text_character_count"], 0
        )

    def test_corrupt_screenshot_does_not_crash(self):
        result = extract_ocr(
            observation_id="test-003",
            run_id="ocr-test-run",
            screenshot_bytes=b"not a valid image",
        )

        self.assertEqual(result["status"], "skipped")
        warning_codes = [
            warning["code"] for warning in result["warnings"]
        ]
        self.assertIn("W_OCR_INVALID_IMAGE", warning_codes)

    def test_blank_image_is_skipped_without_running_tesseract(self):
        image = Image.new("RGB", (100, 100), "white")
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        with patch(
            "modules.ocr_extractor.extractor.pytesseract.image_to_data"
        ) as run_ocr:
            result = extract_ocr(
                "test-blank", "ocr-test-run", screenshot_bytes=buffer.getvalue()
            )
        run_ocr.assert_not_called()
        self.assertEqual(result["status"], "skipped")
        self.assertIn(
            "W_OCR_IMAGE_BLANK",
            [warning["code"] for warning in result["warnings"]],
        )

    def test_unsupported_image_uses_precomputed_fallback(self):
        result = extract_ocr(
            "test-unsupported",
            "ocr-test-run",
            ocr_text="Sign in to continue",
            screenshot_bytes=b"not an image",
        )
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["result"]["source"], "precomputed_text")
        self.assertEqual(result["result"]["text_character_count"], 19)

    def test_missing_tesseract_uses_precomputed_fallback(self):
        from modules.ocr_extractor.extractor import pytesseract

        image_bytes = self.make_test_screenshot()
        with patch(
            "modules.ocr_extractor.extractor.pytesseract.image_to_data",
            side_effect=pytesseract.TesseractNotFoundError(),
        ):
            result = extract_ocr(
                "test-no-tesseract",
                "ocr-test-run",
                ocr_text="Enter password",
                screenshot_bytes=image_bytes,
            )
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["result"]["source"], "precomputed_text")
        self.assertIn(
            "W_OCR_ENGINE_MISSING",
            [warning["code"] for warning in result["warnings"]],
        )

    def test_precomputed_text_still_works(self):
        result = extract_ocr(
            observation_id="test-004",
            run_id="ocr-test-run",
            ocr_text="Login with your email and password",
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(
            result["result"]["source"], "precomputed_text"
        )
        self.assertIn(
            "password",
            result["result"]["extracted_credentials_keywords"],
        )


if __name__ == "__main__":
    unittest.main()
