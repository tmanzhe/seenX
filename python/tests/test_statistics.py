"""Known Wilson examples and edge conditions; no optional dependencies."""

import unittest

from seenx.statistics import wilson_interval


class WilsonIntervalTests(unittest.TestCase):
    def test_known_half_success_example(self):
        lower, upper = wilson_interval(5, 10)
        self.assertAlmostEqual(lower, 0.2365930905)
        self.assertAlmostEqual(upper, 0.7634069095)

    def test_zero_and_all_successes_keep_finite_nonzero_width(self):
        lower, upper = wilson_interval(0, 10)
        self.assertEqual(lower, 0)
        self.assertAlmostEqual(upper, 0.2775327999)
        lower, upper = wilson_interval(10, 10)
        self.assertAlmostEqual(lower, 0.7224672001)
        self.assertEqual(upper, 1)
        self.assertLess(wilson_interval(0, 1)[1], 1)
        self.assertGreater(wilson_interval(1, 1)[0], 0)

    def test_no_trials_is_undefined(self):
        self.assertIsNone(wilson_interval(0, 0))

    def test_higher_confidence_widens_and_more_trials_narrow(self):
        low, high = wilson_interval(5, 10, 0.9)
        wider_low, wider_high = wilson_interval(5, 10, 0.99)
        self.assertLess(wider_low, low)
        self.assertGreater(wider_high, high)
        self.assertGreater(wilson_interval(50, 100)[0], low)
        self.assertLess(wilson_interval(50, 100)[1], high)

    def test_invalid_counts_and_confidence_are_rejected(self):
        for counts in ((-1, 10), (11, 10), (0, -1), (True, 1), (0, False), (0.5, 1), (0, 1.0)):
            with self.subTest(counts=counts), self.assertRaises(ValueError):
                wilson_interval(*counts)
        for confidence in (0, 1, -0.1, float("nan"), float("inf"), True, "0.95", None):
            with self.subTest(confidence=confidence), self.assertRaises(ValueError):
                wilson_interval(0, 0, confidence)


if __name__ == "__main__":
    unittest.main()
