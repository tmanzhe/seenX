"""Metric arithmetic uses explicit rankings, without models or private inputs."""

import unittest

from seenx.retrieval_metrics import recall_at_k, reciprocal_rank, summarize_queries


class RecallTests(unittest.TestCase):
    def test_multiple_relevant_items_and_cutoff_boundary(self):
        ranked = ["irrelevant", "a", "b", "c"]
        relevant = {"a", "b", "missing"}
        self.assertEqual(recall_at_k(ranked, relevant, 1), 0)
        self.assertAlmostEqual(recall_at_k(ranked, relevant, 2), 1 / 3)
        self.assertAlmostEqual(recall_at_k(ranked, relevant, 3), 2 / 3)
        self.assertAlmostEqual(recall_at_k(ranked, relevant, 100), 2 / 3)

    def test_duplicate_ids_do_not_inflate_hits_or_denominator(self):
        self.assertEqual(recall_at_k(["a", "a", "b"], ["a", "a", "b"], 2), 0.5)
        self.assertEqual(recall_at_k(["a", "a", "b"], ["a", "b"], 3), 1)

    def test_empty_rankings_and_no_match_judgments_are_distinct(self):
        self.assertEqual(recall_at_k([], {"a"}, 5), 0)
        self.assertIsNone(recall_at_k([], [], 5))
        self.assertIsNone(recall_at_k(["wrong"], [], 5))

    def test_invalid_k(self):
        for k in (0, -1, 1.5, True):
            with self.subTest(k=k), self.assertRaises(ValueError):
                recall_at_k([], [], k)


class ReciprocalRankTests(unittest.TestCase):
    def test_first_relevant_rank_only(self):
        self.assertEqual(reciprocal_rank(["a", "b"], {"a", "b"}), 1)
        self.assertAlmostEqual(reciprocal_rank(["x", "y", "b", "a"], {"a", "b"}), 1 / 3)

    def test_misses_empty_rankings_and_no_match_queries(self):
        self.assertEqual(reciprocal_rank(["x"], {"a"}), 0)
        self.assertEqual(reciprocal_rank([], {"a"}), 0)
        self.assertIsNone(reciprocal_rank([], []))
        self.assertIsNone(reciprocal_rank(["wrong"], []))

    def test_exact_ids_keep_images_pages_and_regions_distinct(self):
        self.assertEqual(reciprocal_rank(["image.jpg"], {"region:one"}), 0)
        self.assertEqual(reciprocal_rank(["doc.pdf#page=1"], {"doc.pdf#page=2"}), 0)


class SummaryTests(unittest.TestCase):
    def test_macro_mean_includes_positive_misses_and_excludes_no_match_queries(self):
        rows = [
            {"relevant_ids": ["a", "b"], "ranked_ids": ["x", "a", "b"]},
            {"relevant_ids": ["c"], "ranked_ids": ["c"]},
            {"relevant_ids": ["d"], "ranked_ids": []},
            {"relevant_ids": [], "ranked_ids": []},
            {"relevant_ids": [], "ranked_ids": ["false", "also-false"]},
        ]
        summary = summarize_queries(rows, [1, 2, 3])
        self.assertEqual(summary["positive_queries"], 3)
        self.assertAlmostEqual(summary["recall_at_k"]["1"], 1 / 3)
        self.assertAlmostEqual(summary["recall_at_k"]["2"], 0.5)
        self.assertAlmostEqual(summary["recall_at_k"]["3"], 2 / 3)
        self.assertAlmostEqual(summary["mrr"], 0.5)
        self.assertEqual(summary["no_match_queries"], 2)
        self.assertEqual(summary["no_match_false_positives"], 1)
        self.assertEqual(summary["no_match_correct_empty"], 1)
        self.assertEqual(summary["no_match_false_positive_rate"], 0.5)

    def test_no_positive_labels_are_undefined_instead_of_perfect_or_zero(self):
        summary = summarize_queries([{"relevant_ids": [], "ranked_ids": []}], [5])
        self.assertEqual(summary["recall_at_k"], {"5": None})
        self.assertIsNone(summary["mrr"])
        self.assertEqual(summary["no_match_false_positive_rate"], 0)

    def test_no_negative_labels_and_empty_population(self):
        summary = summarize_queries([{"relevant_ids": ["a"], "ranked_ids": ["a"]}], [1])
        self.assertEqual(summary["mrr"], 1)
        self.assertIsNone(summary["no_match_false_positive_rate"])
        summary = summarize_queries([], [1])
        self.assertIsNone(summary["mrr"])
        self.assertIsNone(summary["recall_at_k"]["1"])
        self.assertIsNone(summary["no_match_false_positive_rate"])

    def test_summary_validates_k_even_without_positive_queries(self):
        for ks in ([], [0], [-1]):
            with self.subTest(ks=ks), self.assertRaises(ValueError):
                summarize_queries([], ks)


if __name__ == "__main__":
    unittest.main()
