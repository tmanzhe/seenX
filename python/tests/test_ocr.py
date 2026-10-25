"""Check OCR wiring with existing files and mocked recognition, not generated images."""

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from seenx.image_ocr import check_ocr_available
from seenx.load_images import inspect_image


class OcrTests(unittest.TestCase):
    def test_non_macos_has_a_clear_error(self):
        with patch.object(sys, "platform", "linux"):
            with self.assertRaisesRegex(RuntimeError, "requires macOS"):
                check_ocr_available()

    def test_missing_optional_dependency_has_install_instructions(self):
        with patch.object(sys, "platform", "darwin"):
            with patch.dict(sys.modules, {"Vision": None}):
                with self.assertRaisesRegex(RuntimeError, "uv sync"):
                    check_ocr_available()

    def test_image_records_distinguish_disabled_empty_and_failed_ocr(self):
        # Personal images are optional. No test fixture is copied or committed.
        folder = Path(__file__).resolve().parents[2] / "practice-images"
        image = next(folder.glob("*.jpeg"), None)
        if image is None:
            self.skipTest("No local JPEG practice image available")
        with patch("seenx.load_images.extract_image_text", return_value="") as recognize:
            plain = inspect_image(image)
            recognize.assert_not_called()
            self.assertNotIn("text", plain)
            empty = inspect_image(image, ocr=True)
            self.assertEqual(empty["text"], "")
            self.assertEqual(empty["text_method"], "apple-vision-ocr")
        with patch("seenx.load_images.extract_image_text", side_effect=RuntimeError("test failure")):
            failed = inspect_image(image, ocr=True)
            self.assertEqual(failed["ocr_error"], "test failure")
            self.assertNotIn("text", failed)
            self.assertGreater(failed["width"], 0)


if __name__ == "__main__":
    unittest.main()
