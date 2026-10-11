import tempfile
import unittest
import zipfile
from pathlib import Path

from modules.dataset_adapter.artifacts import read_artifact


class TestArtifactReader(unittest.TestCase):

    def test_reads_text_from_zip(self):
        with tempfile.TemporaryDirectory() as temp:
            archive_path = Path(temp) / "sample.zip"

            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("record_a/html.txt", "<html>hello</html>")

            observation = {
                "artifacts": {
                    "html": {
                        "relative_path": "record_a/html.txt",
                        "storage_medium": "zip_entry",
                    }
                }
            }

            result = read_artifact(
                archive_path, observation, "html"
            )
            self.assertEqual(result, "<html>hello</html>")

    def test_missing_artifact_returns_none(self):
        observation = {
            "artifacts": {
                "html": {
                    "relative_path": "record_a/missing.html",
                    "storage_medium": "zip_entry",
                }
            }
        }

        with tempfile.TemporaryDirectory() as temp:
            archive_path = Path(temp) / "sample.zip"

            with zipfile.ZipFile(archive_path, "w"):
                pass

            result = read_artifact(
                archive_path, observation, "html"
            )
            self.assertIsNone(result)

    def test_absent_artifact_reference_returns_none(self):
        result = read_artifact(
            "not_needed.zip", {"artifacts": {}}, "html"
        )
        self.assertIsNone(result)
    def test_reads_binary_screenshot(self):
        from modules.dataset_adapter.artifacts import read_artifact_bytes

        image_bytes = b"\x89PNG\r\n\x1a\nFAKE"

        with tempfile.TemporaryDirectory() as temp:
            archive_path = Path(temp) / "sample.zip"

            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("record_a/shot.png", image_bytes)

            observation = {
                "artifacts": {
                    "screenshot": {
                        "relative_path": "record_a/shot.png",
                        "format": "png",
                    }
                }
            }

            result = read_artifact_bytes(
                archive_path, observation, "screenshot"
            )
            self.assertEqual(result, image_bytes)

    def test_reads_nested_yolo_coordinates(self):
        with tempfile.TemporaryDirectory() as temp:
            archive_path = Path(temp) / "sample.zip"

            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr(
                    "record_a/yolo_coords.txt", "10 20 100 120"
                )

            observation = {
                "artifacts": {
                    "auxiliary": {
                        "yolo_coords_path": "record_a/yolo_coords.txt"
                    }
                }
            }

            result = read_artifact(
                archive_path, observation, "yolo_coords"
            )
            self.assertEqual(result, "10 20 100 120")



if __name__ == "__main__":
    unittest.main()
