"""Fusion and orchestration tests need neither private files nor model downloads."""

from contextlib import redirect_stdout
from io import StringIO
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from seenx.search_files import fuse_results, search_files, select_paths


class FusionTests(unittest.TestCase):
    def test_matching_both_sources_boosts_and_merges_an_image(self):
        text = [{"path": "both.jpg", "page": None}]
        visual = [{"path": "visual.jpg", "score": 0.9},
                  {"path": "both.jpg", "score": 0.2}]
        results = fuse_results(text, visual, 5)
        self.assertEqual([result["path"] for result in results], ["both.jpg", "visual.jpg"])
        self.assertAlmostEqual(results[0]["score"], 1 / 61 + 1 / 62)
        self.assertEqual([item["method"] for item in results[0]["evidence"]],
                         ["image-ocr", "clip-visual"])
        self.assertEqual(results[0]["evidence"][1]["cosine"], 0.2)

    def test_duplicate_matches_do_not_inflate_a_score(self):
        text = [{"path": "x.jpg", "page": None}] * 2
        visual = [{"path": "x.jpg", "score": 0.5}] * 2
        results = fuse_results(text, visual, 5)
        self.assertEqual(len(results), 1)
        self.assertAlmostEqual(results[0]["score"], 2 / 61)
        self.assertEqual(len(results[0]["evidence"]), 2)

    def test_pdf_pages_stay_separate_and_text_matches_are_tied(self):
        text = [{"path": "doc.pdf", "page": 2}, {"path": "doc.pdf", "page": 1}]
        results = fuse_results(text, [], 5)
        self.assertEqual([result["page"] for result in results], [1, 2])
        self.assertEqual(results[0]["score"], results[1]["score"])
        self.assertEqual(results[0]["evidence"][0]["method"], "pdf-text")

    def test_single_modes_ignore_the_other_source(self):
        text = [{"path": "doc.pdf", "page": 1}]
        visual = [{"path": "x.jpg", "score": -0.2}]
        exact = fuse_results(text, visual, 5, "text")
        self.assertEqual(len(exact), 1)
        self.assertEqual(exact[0]["score_kind"], "exact-match")
        image = fuse_results(text, visual, 5, "visual")
        self.assertEqual(len(image), 1)
        self.assertEqual(image[0]["score"], -0.2)
        self.assertEqual(image[0]["score_kind"], "cosine")

    def test_limits_empty_results_and_input_validation(self):
        self.assertEqual(fuse_results([], [], 5), [])
        matches = [{"path": name, "page": None} for name in ("b.jpg", "a.jpg")]
        self.assertEqual(fuse_results(matches, [], 1)[0]["path"], "a.jpg")
        with self.assertRaises(ValueError):
            fuse_results([], [], 0)


class SearchFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name).resolve()
        # Only placeholders for discovery. Readers are mocked below.
        for name in ("a.pdf", "b.jpg", "c.jpg", "ignore.txt"):
            (self.folder / name).write_text("placeholder")
        self.text = [{"path": str(self.folder / "a.pdf"), "kind": "pdf", "pages": [
            {"number": 1, "text": "train booking"},
        ]}]

    def test_candidate_limit_is_shared_by_both_branches(self):
        encoder = Mock()
        encoder.encode_text.return_value = [1, 0]
        vectors = [{"path": str(self.folder / "b.jpg"), "embedding": [1, 0]}]
        with redirect_stdout(StringIO()), patch("seenx.search_files.read_folder", return_value=self.text) as reader:
            with patch("seenx.search_files.collect_embeddings", return_value=vectors) as collect:
                results = search_files(self.folder, "booking", limit=2, encoder=encoder)
        self.assertEqual(reader.call_args.kwargs["paths"],
                         [self.folder / "a.pdf", self.folder / "b.jpg"])
        self.assertEqual(collect.call_args.kwargs["paths"], [self.folder / "b.jpg"])
        self.assertFalse(reader.call_args.kwargs["show_summaries"])
        self.assertEqual(len(results), 2)

    def test_weak_visual_candidates_are_filtered_before_fusion(self):
        encoder = Mock()
        encoder.encode_text.return_value = [1, 0]
        vectors = [
            {"path": str(self.folder / "b.jpg"), "embedding": [0.3, math.sqrt(1 - 0.3 ** 2)]},
            {"path": str(self.folder / "c.jpg"), "embedding": [0.2, math.sqrt(1 - 0.2 ** 2)]},
        ]
        with redirect_stdout(StringIO()), patch("seenx.search_files.read_folder", return_value=self.text):
            with patch("seenx.search_files.collect_embeddings", return_value=vectors):
                results = search_files(self.folder, "booking", encoder=encoder)
                strict = search_files(self.folder, "booking", encoder=encoder, min_score=0.5)
        self.assertEqual({Path(result["path"]).name for result in results}, {"a.pdf", "b.jpg"})
        self.assertEqual(len(strict), 1)
        self.assertEqual(strict[0]["evidence"][0]["method"], "pdf-text")

    def test_rejected_visual_evidence_does_not_remove_an_exact_ocr_match(self):
        encoder = Mock()
        encoder.encode_text.return_value = [1, 0]
        image_path = str(self.folder / "b.jpg")
        text = [{"path": image_path, "kind": "image", "text": "booking"}]
        vectors = [{"path": image_path, "embedding": [0, 1]}]
        with redirect_stdout(StringIO()), patch("seenx.search_files.read_folder", return_value=text):
            with patch("seenx.search_files.collect_embeddings", return_value=vectors):
                results = search_files(self.folder, "booking", encoder=encoder)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["evidence"], [{"method": "image-ocr", "rank": 1}])

    def test_text_mode_does_not_load_clip(self):
        with redirect_stdout(StringIO()), patch("seenx.search_files.read_folder", return_value=self.text):
            with patch("seenx.search_files.ClipEncoder", side_effect=AssertionError("model loaded")):
                results = search_files(self.folder, "booking", mode="text")
        self.assertEqual(results[0]["page"], 1)

    def test_pdf_only_selection_does_not_load_clip_in_hybrid_mode(self):
        with redirect_stdout(StringIO()), patch("seenx.search_files.read_folder", return_value=self.text):
            with patch("seenx.search_files.ClipEncoder", side_effect=AssertionError("model loaded")):
                results = search_files(self.folder, "booking", mode="hybrid", limit=1)
        self.assertEqual(results[0]["evidence"][0]["method"], "pdf-text")

    def test_visual_mode_does_not_read_pdf_text(self):
        encoder = Mock()
        encoder.encode_text.return_value = [1, 0]
        vectors = [{"path": str(self.folder / "b.jpg"), "embedding": [1, 0]}]
        with redirect_stdout(StringIO()), patch("seenx.search_files.read_folder", side_effect=AssertionError("text reader called")):
            with patch("seenx.search_files.collect_embeddings", return_value=vectors):
                results = search_files(self.folder, "laptop", mode="visual", encoder=encoder)
        self.assertEqual(results[0]["score_kind"], "cosine")

    def test_visual_selection_only_includes_images(self):
        self.assertEqual(select_paths(self.folder, "visual", 1), [self.folder / "b.jpg"])

    def test_invalid_options_and_unreadable_collection(self):
        for options in ({"query": " "}, {"limit": 0}, {"min_score": math.nan},
                        {"mode": "visual", "ocr": True},
                        {"mode": "text", "download": True}):
            arguments = {"query": "booking", **options}
            with self.subTest(options=options), self.assertRaises(ValueError):
                search_files(self.folder, **arguments)
        with redirect_stdout(StringIO()), patch("seenx.search_files.read_folder", return_value=[]):
            with self.assertRaisesRegex(ValueError, "could be read"):
                search_files(self.folder, "booking", mode="text")


if __name__ == "__main__":
    unittest.main()
