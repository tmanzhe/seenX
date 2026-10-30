"""Retrieval metrics over ordered evidence IDs; no model dependencies."""

from collections.abc import Collection, Sequence
from statistics import fmean

from seenx.statistics import wilson_interval


def recall_at_k(ranked_ids: Sequence[str], relevant_ids: Collection[str],
                k: int) -> float | None:
    """Fraction of distinct relevant IDs present in the first k results.

    No-match queries have no recall denominator and return None.
    """
    if type(k) is not int or k < 1:
        raise ValueError("k must be a positive integer")
    relevant = set(relevant_ids)
    if not relevant:
        return None
    return len(set(ranked_ids[:k]) & relevant) / len(relevant)


def reciprocal_rank(ranked_ids: Sequence[str],
                    relevant_ids: Collection[str]) -> float | None:
    """Reciprocal of the first relevant rank in the full accepted ranking."""
    relevant = set(relevant_ids)
    if not relevant:
        return None
    for rank, result_id in enumerate(ranked_ids, start=1):
        if result_id in relevant:
            return 1 / rank
    return 0.0


def recall_counts_at_k(ranked_ids: Sequence[str], relevant_ids: Collection[str], k: int) -> tuple[int, int]:
    """Distinct retrieved/relevant counts for a query's binomial recall estimate."""
    recall_at_k([], [], k)
    relevant = set(relevant_ids)
    return len(set(ranked_ids[:k]) & relevant), len(relevant)


def recall_estimate(hits: int, total: int) -> dict:
    """Keep the point estimate, denominator, and its 95% interval together."""
    interval = wilson_interval(hits, total)
    return {"value": hits / total if total else None, "hits": hits, "total": total,
            "interval": list(interval) if interval is not None else None}


def summarize_queries(rows: Sequence[dict], ks: Sequence[int]) -> dict:
    """Macro-average positives and report pooled recall with Wilson bounds.

    Each row contains relevant_ids and ranked_ids. Missing relevant hits score
    zero; no-match queries are separate. An empty positive-query population is
    undefined, represented by None. Only pooled counts get a binomial interval.
    """
    if not ks:
        raise ValueError("At least one k is required")
    for k in ks:
        recall_at_k([], [], k)
    positive = [row for row in rows if row["relevant_ids"]]
    negative = [row for row in rows if not row["relevant_ids"]]
    false_positives = sum(bool(row["ranked_ids"]) for row in negative)
    return {
        "positive_queries": len(positive),
        "recall_at_k": {
            str(k): fmean(recall_at_k(row["ranked_ids"], row["relevant_ids"], k)
                          for row in positive) if positive else None
            for k in ks
        },
        "micro_recall_at_k": {
            str(k): recall_estimate(
                sum(recall_counts_at_k(row["ranked_ids"], row["relevant_ids"], k)[0] for row in positive),
                sum(len(set(row["relevant_ids"])) for row in positive),
            ) for k in ks
        },
        "mrr": fmean(reciprocal_rank(row["ranked_ids"], row["relevant_ids"])
                     for row in positive) if positive else None,
        "no_match_queries": len(negative),
        "no_match_false_positives": false_positives,
        "no_match_correct_empty": len(negative) - false_positives,
        "no_match_false_positive_rate": false_positives / len(negative) if negative else None,
    }
