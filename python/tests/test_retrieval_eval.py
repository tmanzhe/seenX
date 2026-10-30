"""Evaluation delegates ranking; fake files are never decoded by these tests."""

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from seenx.retrieval_eval import evaluate, load_labels, main, result_id


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name).resolve()
        for name in ("a.jpg", "b.jpg", "c.jpg", "doc.pdf"):
            (self.folder / name).write_text("discovery placeholder", encoding="utf-8")
        self.labels = {
            "version": 1, "name": "test labels", "status": "starter",
            "queries": [
                {"id": "positive", "query": "example", "relevant_ids": ["c.jpg"],
                 "evidence": "Synthetic judgment for a mocked ranking."},
                {"id": "negative", "query": "no match", "relevant_ids": [],
                 "evidence": "Synthetic negative judgment."},
            ],
        }

    def hits(self, *names):
        return [{"path": str(self.folder / name), "page": None,
                 "score": 0.5, "score_kind": "cosine",
                 "evidence": [{"method": "clip-visual", "rank": rank}]}
                for rank, name in enumerate(names, start=1)]

    def write_labels(self, labels):
        path = self.folder / "labels.json"
        path.write_text(json.dumps(labels), encoding="utf-8")
        return path

    def test_all_modes_reuse_search_order_and_full_ranking_for_mrr(self):
        encoder = Mock(cache_key="test-pinned-model")
        positive = self.hits("b.jpg", "a.jpg", "c.jpg")
        with patch("seenx.retrieval_eval.ClipEncoder", return_value=encoder) as load:
            with patch("seenx.retrieval_eval.search_files", side_effect=[positive, []] * 3) as search:
                report = evaluate(self.folder, self.labels, [1, 2], ocr=True)
        load.assert_called_once_with(download=False)
        self.assertEqual([call.kwargs["mode"] for call in search.call_args_list],
                         ["text", "text", "visual", "visual", "hybrid", "hybrid"])
        self.assertEqual([call.kwargs["ocr"] for call in search.call_args_list],
                         [True, True, False, False, True, True])
        for call in search.call_args_list:
            self.assertEqual(call.kwargs["limit"], 4)
            self.assertEqual(call.kwargs["top_k"], sys.maxsize)
            self.assertEqual(call.kwargs["min_score"], 0.25)
        for mode in ("lexical", "visual", "hybrid"):
            summary = report["modes"][mode]["summary"]
            self.assertEqual(summary["recall_at_k"], {"1": 0, "2": 0})
            self.assertAlmostEqual(summary["mrr"], 1 / 3)
            row = report["modes"][mode]["queries"][0]
            self.assertEqual(row["ranked_ids"], ["b.jpg", "a.jpg", "c.jpg"])
            self.assertEqual(row["results"][0]["evidence"], positive[0]["evidence"])
        self.assertIsNone(report["confidence_intervals"])
        self.assertTrue(any("Wilson" in note for note in report["metric_notes"]))

    def test_lexical_only_never_loads_visual_model(self):
        with patch("seenx.retrieval_eval.ClipEncoder", side_effect=AssertionError("model loaded")):
            with patch("seenx.retrieval_eval.search_files", return_value=[]):
                report = evaluate(self.folder, self.labels, [5], ["lexical"])
        self.assertIsNone(report["settings"]["model_id"])
        self.assertEqual(report["modes"]["lexical"]["summary"]["mrr"], 0)

    def test_missing_labeled_file_fails_before_search_or_model_loading(self):
        self.labels["queries"][0]["relevant_ids"] = ["missing.jpg"]
        with patch("seenx.retrieval_eval.ClipEncoder") as load:
            with patch("seenx.retrieval_eval.search_files") as search:
                with self.assertRaisesRegex(ValueError, "Missing labeled source"):
                    evaluate(self.folder, self.labels, [5])
        load.assert_not_called()
        search.assert_not_called()

    def test_negative_only_starter_keeps_pending_queries_unscored(self):
        self.labels["queries"] = self.labels["queries"][1:]
        self.labels["pending_queries"] = [{"query": "unjudged", "reason": "Missing image ID"}]
        self.labels["description"] = "Provisional metadata labels"
        with patch("seenx.retrieval_eval.search_files", return_value=self.hits("a.jpg")) as search:
            report = evaluate(self.folder, self.labels, [1, 5], ["lexical"])
        search.assert_called_once()
        self.assertEqual(search.call_args.args[1], "no match")
        summary = report["modes"]["lexical"]["summary"]
        self.assertEqual(summary["recall_at_k"], {"1": None, "5": None})
        self.assertIsNone(summary["mrr"])
        self.assertEqual(summary["no_match_false_positives"], 1)
        self.assertEqual(report["dataset"]["pending_queries"], self.labels["pending_queries"])
        self.assertEqual(report["dataset"]["description"], self.labels["description"])

    def test_portable_ids_distinguish_pdf_pages(self):
        hit = {"path": str(self.folder / "doc.pdf"), "page": 2}
        self.assertEqual(result_id(hit, self.folder), "doc.pdf#page=2")
        hit = {"path": str(self.folder / "a.jpg"), "page": None}
        self.assertEqual(result_id(hit, self.folder), "a.jpg")

    def test_label_validation_rejects_ambiguous_judgments_and_ids(self):
        for relevant in (None, ["../a.jpg"], ["/a.jpg"], ["a.jpg", "a.jpg"],
                         ["region:one"], ["doc.pdf"], ["doc.pdf#page=0"],
                         ["doc.pdf#page=01"], ["a.jpg#page=1"]):
            self.labels["queries"][0]["relevant_ids"] = relevant
            with self.subTest(relevant=relevant), self.assertRaises(ValueError):
                load_labels(self.write_labels(self.labels))

    def test_labels_accept_images_and_pages_but_not_duplicate_query_ids(self):
        self.labels["queries"][0]["relevant_ids"] = ["a.jpg", "doc.pdf#page=2"]
        self.assertEqual(load_labels(self.write_labels(self.labels)), self.labels)
        self.labels["queries"][1]["id"] = "positive"
        with self.assertRaisesRegex(ValueError, "Duplicate query ID"):
            load_labels(self.write_labels(self.labels))

    def test_cli_stdout_is_one_json_report_and_progress_goes_to_stderr(self):
        path = self.write_labels(self.labels)

        def search(*args, **kwargs):
            print("search progress")
            return []

        output, diagnostics = StringIO(), StringIO()
        arguments = ["seenx-eval", str(self.folder), "--labels", str(path),
                     "--modes", "lexical", "--k", "5", "1"]
        with patch.object(sys, "argv", arguments), redirect_stdout(output), redirect_stderr(diagnostics):
            with patch("seenx.retrieval_eval.search_files", side_effect=search):
                main()
        report = json.loads(output.getvalue())
        self.assertEqual(report["settings"]["k"], [1, 5])
        self.assertEqual(diagnostics.getvalue().count("search progress"), 2)


if __name__ == "__main__":
    unittest.main()
