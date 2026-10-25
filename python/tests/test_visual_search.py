"""Vector arithmetic tests don't download a model or create images."""

import math
import unittest

from seenx.visual_search import filter_visual_matches, normalize_vector, rank_images


class VisualSearchTests(unittest.TestCase):
    def test_default_cutoff_keeps_only_stronger_basketball_and_laptop_matches(self):
        for scores in ([0.2906, 0.2332, 0.2072], [0.2844, 0.2398, 0.2306]):
            matches = [{"path": str(number), "score": score}
                       for number, score in enumerate(scores)]
            self.assertEqual(filter_visual_matches(matches), matches[:1])

    def test_cutoff_can_return_none_or_multiple_without_filling_the_limit(self):
        self.assertEqual(filter_visual_matches([{"score": 0.2087}]), [])
        matches = [{"score": 0.3}, {"score": 0.25}, {"score": 0.2}]
        self.assertEqual(filter_visual_matches(matches), matches[:2])
        self.assertEqual(filter_visual_matches(matches, 0.35), [])
        self.assertEqual(filter_visual_matches(matches, -1), matches)

    def test_cutoff_rejects_invalid_numbers(self):
        for cutoff in (math.nan, math.inf, -math.inf, -1.1, 1.1):
            with self.subTest(cutoff=cutoff), self.assertRaises(ValueError):
                filter_visual_matches([], cutoff)

    def test_normalization_preserves_direction_and_makes_unit_length(self):
        vector = normalize_vector([3, 4])
        self.assertAlmostEqual(vector[0], 0.6)
        self.assertAlmostEqual(vector[1], 0.8)
        self.assertAlmostEqual(sum(value * value for value in vector), 1)

    def test_invalid_vectors_are_rejected(self):
        for vector in ([], [0, 0], [math.nan, 1], [math.inf, 1]):
            with self.subTest(vector=vector), self.assertRaises(ValueError):
                normalize_vector(vector)

    def test_ranking_and_scores_use_cosine_not_magnitude(self):
        records = [
            {"path": "opposite.jpg", "embedding": [-1, 0]},
            {"path": "unrelated.jpg", "embedding": [0, 100]},
            {"path": "closest.jpg", "embedding": [3, 0]},
        ]
        self.assertEqual(rank_images(records, [10, 0], 2), [
            {"path": "closest.jpg", "score": 1.0},
            {"path": "unrelated.jpg", "score": 0.0},
        ])
        self.assertEqual(rank_images(records, [10, 0], 3)[2]["score"], -1)

    def test_ties_have_repeatable_path_order_and_empty_collection_is_valid(self):
        records = [{"path": path, "embedding": [1, 0]} for path in ("b.jpg", "a.jpg")]
        self.assertEqual(rank_images(records, [1, 0], 5)[0]["path"], "a.jpg")
        self.assertEqual(rank_images([], [1, 0], 5), [])

    def test_dimensions_and_result_limit_are_checked(self):
        with self.assertRaises(ValueError):
            rank_images([{"path": "x.jpg", "embedding": [1, 0]}], [1], 5)
        with self.assertRaises(ValueError):
            rank_images([], [1, 0], 0)


if __name__ == "__main__":
    unittest.main()
