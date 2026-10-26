"""Check OCR wiring with existing files and mocked recognition, not generated images."""

from pathlib import Path
import math
import sys
import unittest
from unittest.mock import patch

from seenx.image_ocr import check_ocr_available, extract_image_text, vision_box_to_top_left
from seenx.load_images import inspect_image


class OcrTests(unittest.TestCase):
    def test_box_conversion_flips_vertical_origin_without_changing_extent(self):
        box = vision_box_to_top_left(0.1, 0.7, 0.3, 0.1)
        self.assertAlmostEqual(box["x"], 0.1)
        self.assertAlmostEqual(box["y"], 0.2)
        self.assertAlmostEqual(box["width"], 0.3)
        self.assertAlmostEqual(box["height"], 0.1)
        self.assertEqual(vision_box_to_top_left(0, 0, 1, 1), {"x": 0, "y": 0, "width": 1, "height": 1})

    def test_invalid_or_nonfinite_boxes_are_rejected(self):
        for box in ((0, 0, math.nan, 1), (-0.1, 0, 1, 1), (0.8, 0, 0.3, 1),
                    (0, 0, 0, 1), (-1e-10, 0, 5e-11, 1)):
            with self.subTest(box=box), self.assertRaises(ValueError):
                vision_box_to_top_left(*box)

    def test_string_interface_still_joins_observations_in_order(self):
        with patch("seenx.image_ocr.extract_image_observations", return_value={"observations": [
            {"text": "First"}, {"text": "Second"},
        ]}):
            self.assertEqual(extract_image_text(object()), "First\nSecond")

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
