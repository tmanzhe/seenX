"""Evaluate labeled folder queries using the existing retrieval ranking."""

import argparse
from contextlib import redirect_stdout
import json
from pathlib import Path, PurePosixPath
import platform
import sqlite3
import sys

from seenx.paths import CACHE_PATH
from seenx.record_cache import open_cache
from seenx.retrieval_metrics import recall_at_k, reciprocal_rank, summarize_queries
from seenx.search_files import search_files, select_paths
from seenx.visual_search import (
    ClipEncoder, DEFAULT_MIN_SCORE, EXTENSIONS, MODEL_ID, MODEL_REVISION,
    filter_visual_matches,
)


MODES = {"lexical": "text", "visual": "visual", "hybrid": "hybrid"}
INTERVAL_NOTE = (
    "Wilson intervals unavailable: no shared Wilson interval helper exists in "
    "the repository. No statistical interval implementation was added."
)


def _nonblank(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _source_name(result_id: str) -> str:
    """Validate a flat-folder image ID or a one-based PDF-page ID."""
    if not _nonblank(result_id):
        raise ValueError("Relevant IDs must be nonblank strings")
    name, separator, page = result_id.partition("#page=")
    path = PurePosixPath(name)
    if (path.is_absolute() or len(path.parts) != 1 or path.name != name
            or name in {".", ".."} or "\\" in name):
        raise ValueError(f"IDs must use a filename in the input folder: {result_id}")
    if separator:
        if path.suffix.lower() != ".pdf" or not page.isascii() or not page.isdecimal() or int(page) < 1:
            raise ValueError(f"Invalid PDF-page ID: {result_id}")
        if str(int(page)) != page:
            raise ValueError(f"Page IDs must use canonical one-based integers: {result_id}")
    elif path.suffix.lower() not in EXTENSIONS:
        raise ValueError(f"Expected an image ID or PDF filename#page=N: {result_id}")
    return name


def load_labels(path: Path) -> dict:
    """Read version-1 labels, rejecting ambiguous or incomplete judgments."""
    labels = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(labels, dict) or type(labels.get("version")) is not int or labels["version"] != 1:
        raise ValueError("Labels must be a JSON object with version 1")
    if not _nonblank(labels.get("name")) or labels.get("status") not in ("starter", "reviewed"):
        raise ValueError("Labels require a name and status (starter or reviewed)")
    queries = labels.get("queries")
    if not isinstance(queries, list) or not queries:
        raise ValueError("Labels require at least one judged query")
    seen = set()
    for row in queries:
        if not isinstance(row, dict) or not all(_nonblank(row.get(key)) for key in ("id", "query", "evidence")):
            raise ValueError("Each query requires nonblank id, query, and evidence strings")
        if row["id"] in seen:
            raise ValueError(f"Duplicate query ID: {row['id']}")
        seen.add(row["id"])
        relevant = row.get("relevant_ids")
        if not isinstance(relevant, list):
            raise ValueError("Each query requires relevant_ids; [] explicitly means no match")
        for result_id in relevant:
            _source_name(result_id)
        if len(set(relevant)) != len(relevant):
            raise ValueError(f"Duplicate relevant IDs for query: {row['id']}")
    pending = labels.get("pending_queries", [])
    if not isinstance(pending, list):
        raise ValueError("pending_queries must be a list of unjudged query descriptions")
    return labels


def result_id(result: dict, folder: Path) -> str:
    """Preserve image/page identity without leaking machine-specific paths."""
    name = Path(result["path"]).relative_to(folder).as_posix()
    if "#page=" in name:
        raise ValueError("Filenames containing #page= are reserved by the label format")
    page = result["page"]
    return name if page is None else f"{name}#page={page}"


def evaluate(folder: Path, labels: dict, ks: list[int],
             modes: list[str] | None = None, *, ocr: bool = False,
             cache=None, download: bool = False,
             min_score: float = DEFAULT_MIN_SCORE) -> dict:
    """Run complete accepted rankings, leaving all scores and ordering intact."""
    modes = list(MODES) if modes is None else modes
    if not modes or any(mode not in MODES for mode in modes) or len(set(modes)) != len(modes):
        raise ValueError("Choose unique modes from lexical, visual, hybrid")
    # Validate cutoffs before loading any optional model or reading image pixels.
    summarize_queries([], ks)
    filter_visual_matches([], min_score)
    folder = folder.expanduser().resolve()
    if not folder.is_dir():
        raise ValueError(f"Not a folder: {folder}; practice-images is ignored by Git")
    paths = select_paths(folder, "hybrid", sys.maxsize)
    if not paths:
        raise ValueError("No supported files in the input folder")
    names = {path.name for path in paths}
    if any("#page=" in name for name in names):
        raise ValueError("Filenames containing #page= are reserved by the label format")
    for row in labels["queries"]:
        for relevant_id in row["relevant_ids"]:
            if _source_name(relevant_id) not in names:
                raise ValueError(f"Missing labeled source for {row['id']}: {relevant_id}")
    images = [path for path in paths if path.suffix.lower() in EXTENSIONS]
    if "visual" in modes and not images:
        raise ValueError("Visual evaluation needs at least one supported image")
    if download and not any(mode in {"visual", "hybrid"} for mode in modes):
        raise ValueError("--download-model requires visual or hybrid evaluation")
    report = {
        "version": 1,
        "dataset": {
            "name": labels["name"], "status": labels["status"],
            "description": labels.get("description"),
            "judged_queries": len(labels["queries"]),
            "pending_queries": labels.get("pending_queries", []),
        },
        "settings": {
            "k": ks, "modes": modes, "ocr": ocr,
            "min_score": min_score, "cache_enabled": cache is not None,
            "download_model": download, "candidate_limit": len(paths),
            "corpus_ids": sorted(names),
            "python": platform.python_version(), "platform": platform.platform(),
            "model_id": None, "model_revision": None, "encoder_cache_key": None,
        },
        "metric_notes": [
            "recall_at_k and mrr are macro means over positive queries only; null means no positive judgments.",
            "MRR uses the full accepted ranking, after the existing cutoff and fusion, with no k truncation.",
            "No-match queries are counted separately; any returned result is a false positive.",
            "Lexical is the existing folder text mode (literal PDF/OCR phrases), not catalog FTS5.",
            "Image/page IDs are scored exactly; this evaluator does not retrieve or score saved regions or notes.",
            INTERVAL_NOTE,
        ],
        "confidence_intervals": None,
        "modes": {},
    }
    if not any(row["relevant_ids"] for row in labels["queries"]):
        report["metric_notes"].append(
            "This label set has no positive judgments; add verified image IDs before comparing recall or MRR."
        )
    encoder = None
    # The existing search readers print progress. Keep stdout a single JSON report.
    with redirect_stdout(sys.stderr):
        for mode in modes:
            if mode in {"visual", "hybrid"} and images and encoder is None:
                encoder = ClipEncoder(download=download)
                report["settings"].update(
                    model_id=MODEL_ID, model_revision=MODEL_REVISION,
                    encoder_cache_key=encoder.cache_key,
                )
            rows = []
            for labeled in labels["queries"]:
                results = search_files(
                    folder, labeled["query"], mode=MODES[mode],
                    ocr=ocr and mode != "visual", limit=len(paths),
                    top_k=sys.maxsize, cache=cache, encoder=encoder,
                    min_score=min_score,
                )
                ranked_ids = [result_id(result, folder) for result in results]
                relevant = labeled["relevant_ids"]
                rows.append({
                    "id": labeled["id"], "query": labeled["query"],
                    "evidence": labeled["evidence"], "relevant_ids": relevant,
                    "ranked_ids": ranked_ids,
                    "recall_at_k": {str(k): recall_at_k(ranked_ids, relevant, k) for k in ks},
                    "reciprocal_rank": reciprocal_rank(ranked_ids, relevant),
                    "no_match_false_positive": bool(ranked_ids) if not relevant else None,
                    "results": [
                        {"id": item_id, "score": item["score"],
                         "score_kind": item["score_kind"], "evidence": item["evidence"]}
                        for item_id, item in zip(ranked_ids, results)
                    ],
                })
            report["modes"][mode] = {"summary": summarize_queries(rows, ks), "queries": rows}
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--labels", required=True, type=Path, help="Version-1 labeled-query JSON file")
    parser.add_argument("--k", nargs="+", type=int, default=[1, 5, 10], help="Positive recall cutoffs")
    parser.add_argument("--modes", nargs="+", choices=list(MODES), default=list(MODES))
    parser.add_argument("--ocr", action="store_true", help="Include image words in lexical/hybrid modes (macOS)")
    parser.add_argument("--cache", action="store_true", help="Reuse the existing extraction/embedding cache")
    parser.add_argument("--download-model", action="store_true", help="Allow the existing pinned CLIP model download")
    parser.add_argument("--min-score", type=float, default=DEFAULT_MIN_SCORE)
    args = parser.parse_args()
    try:
        labels = load_labels(args.labels)
        with open_cache(CACHE_PATH if args.cache else None) as cache:
            report = evaluate(
                args.folder, labels, sorted(set(args.k)), args.modes,
                ocr=args.ocr, cache=cache, download=args.download_model,
                min_score=args.min_score,
            )
    except (ValueError, RuntimeError, ImportError, OSError, sqlite3.Error) as error:
        parser.exit(1, f"Evaluation failed: {error}\n")
    print(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
