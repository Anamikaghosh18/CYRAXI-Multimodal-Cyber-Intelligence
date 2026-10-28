import io
import unittest

from PIL import Image

from modules.cv_detector.detector import detect_logo_candidates


class TestCVDetector(unittest.TestCase):
    def setUp(self):
        image = Image.new("RGB", (64, 48), "white")
        for x in range(8, 44):
            for y in range(6, 34):
                image.putpixel((x, y), (0, 80, 180))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        self.screenshot_bytes = buffer.getvalue()

    def detect(self, coordinates_text=None, screenshot_bytes=None):
        return detect_logo_candidates(
            "obs_0123456789abcdef0123456789abcdef",
            "cv-test-run",
            coordinates_text=coordinates_text,
            screenshot_bytes=(
                self.screenshot_bytes
                if screenshot_bytes is None and coordinates_text
                else screenshot_bytes
            ),
        )

    def warning_codes(self, result):
        return [warning["code"] for warning in result["warnings"]]

    def test_valid_pixel_xyxy_candidate_is_cropped_without_brand_claim(self):
        result = self.detect("8 6 44 34")
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["result"]["classification"]["num_candidates_found"], 1)
        candidate = result["result"]["detected_elements"][0]
        self.assertEqual(candidate["box_2d"], [8, 6, 44, 34])
        self.assertEqual(candidate["crop"]["width"], 36)
        self.assertEqual(candidate["crop"]["height"], 28)
        self.assertIsNone(candidate["detector_confidence"])
        self.assertEqual(candidate["brand_matches"], [])
        self.assertFalse(candidate["brand_identified"])
        self.assertFalse(result["result"]["brand_match_performed"])
        self.assertIn("W_CV_BRAND_MATCH_UNAVAILABLE", self.warning_codes(result))

    def test_observed_archive_tuple_row_crops_and_ignores_source_confidence(self):
        result = self.detect("(8, 6, 44, 34)\t0.95")
        self.assertEqual(result["result"]["classification"]["num_candidates_found"], 1)
        candidate = result["result"]["detected_elements"][0]
        self.assertEqual(candidate["box_2d"], [8, 6, 44, 34])
        self.assertIsNone(candidate["detector_confidence"])
        self.assertFalse(any(
            warning["code"] == "W_CV_COORDINATE_FORMAT_UNVERIFIED"
            for warning in result["warnings"]
        ))

    def test_missing_coordinates_is_skipped(self):
        result = self.detect("")
        self.assertEqual(result["status"], "skipped")
        self.assertIn("W_CV_COORDINATES_MISSING", self.warning_codes(result))

    def test_missing_screenshot_is_skipped(self):
        result = self.detect("8 6 44 34", screenshot_bytes=b"")
        self.assertEqual(result["status"], "skipped")
        self.assertIn("W_CV_SCREENSHOT_MISSING", self.warning_codes(result))

    def test_corrupt_screenshot_returns_warning(self):
        result = self.detect("8 6 44 34", screenshot_bytes=b"bad image")
        self.assertEqual(result["status"], "error")
        self.assertIn("W_CV_INVALID_SCREENSHOT", self.warning_codes(result))

    def test_malformed_coordinate_rows_are_rejected(self):
        result = self.detect("8 nope 44 34\n1 2 3")
        self.assertEqual(result["result"]["detected_elements"], [])
        self.assertEqual(result["result"]["classification"]["num_candidates_found"], 0)
        self.assertEqual(self.warning_codes(result).count("W_CV_INVALID_COORDINATE_LINE"), 2)

    def test_out_of_bounds_or_reversed_boxes_are_rejected(self):
        result = self.detect("0 0 65 20\n20 10 10 30\n0 0 20 49")
        self.assertEqual(result["result"]["detected_elements"], [])
        self.assertEqual(self.warning_codes(result).count("W_CV_INVALID_COORDINATE_LINE"), 3)

    def test_unrecognized_extra_columns_are_rejected(self):
        result = self.detect("8 6 44 34 0.95")
        self.assertEqual(result["result"]["detected_elements"], [])
        self.assertIn("W_CV_INVALID_COORDINATE_LINE", self.warning_codes(result))


if __name__ == "__main__":
    unittest.main()
