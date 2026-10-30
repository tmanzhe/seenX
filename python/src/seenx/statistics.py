"""Small dependency-free statistical helpers for the reference evaluator."""

import math
from statistics import NormalDist


def wilson_interval(successes: int, total: int, confidence: float = 0.95) -> tuple[float, float] | None:
    """Two-sided Wilson score interval for a binomial proportion.

    An empty population is undefined. Counts must be integers; a macro mean of
    fractional query recalls is not a binomial success count.
    """
    if type(successes) is not int or type(total) is not int or not 0 <= successes <= total:
        raise ValueError("Wilson counts must be integers with 0 <= successes <= total")
    if (isinstance(confidence, bool) or not isinstance(confidence, (float, int))
            or not math.isfinite(confidence) or not 0 < confidence < 1):
        raise ValueError("confidence must be finite and between zero and one")
    if total == 0:
        return None
    # The lower tail avoids rounding (1 + confidence) / 2 to one.
    z = -NormalDist().inv_cdf((1 - confidence) / 2)
    z2 = z * z
    proportion = successes / total
    denominator = 1 + z2 / total
    center = (proportion + z2 / (2 * total)) / denominator
    radius = z * math.sqrt(proportion * (1 - proportion) / total + z2 / (4 * total * total)) / denominator
    lower = 0.0 if successes == 0 else max(0.0, center - radius)
    upper = 1.0 if successes == total else min(1.0, center + radius)
    return lower, upper
