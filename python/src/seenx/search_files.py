"""Search one local collection with text, visual similarity, or both."""

import argparse
import logging
from pathlib import Path
import sqlite3

from seenx.paths import CACHE_PATH

from seenx.image_ocr import check_ocr_available
from seenx.load_images import normalize_text, read_folder, search_text
from seenx.record_cache import open_cache
from seenx.visual_search import (ClipEncoder, DEFAULT_MIN_SCORE, EXTENSIONS, MODEL_ID, MODEL_REVISION,
                           collect_embeddings, filter_visual_matches, rank_images)
from seenx.observability import configure_logging, count, event, file_id, observed_search, run_context, stage

FUSION_SMOOTHING = 60


def fuse_results(text_matches: list, visual_matches: list, top_k: int,
                 mode: str = "hybrid") -> list:
    """Use tied rank 1 for exact matches and ranked visual contributions."""
    if top_k < 1 or mode not in {"text", "visual", "hybrid"}:
        raise ValueError("Invalid result limit or search mode")
    results = {}
    if mode in {"text", "hybrid"}:
        for match in text_matches:
            key = (match["path"], match["page"])
            if key in results:
                continue
            method = "pdf-text" if match["page"] is not None else "image-ocr"
            results[key] = {
                "path": match["path"], "page": match["page"],
                "score": 1.0 if mode == "text" else 1 / (FUSION_SMOOTHING + 1),
                "score_kind": "exact-match" if mode == "text" else "rank-fusion",
                "evidence": [{"method": method, "rank": 1}],
            }
    if mode in {"visual", "hybrid"}:
        seen = set()
        for match in visual_matches:
            key = (match["path"], None)
            if key in seen:
                continue
            seen.add(key)
            rank = len(seen)
            evidence = {"method": "clip-visual", "rank": rank, "cosine": match["score"]}
            if key not in results:
                results[key] = {
                    "path": match["path"], "page": None, "score": 0.0,
                    "score_kind": "cosine" if mode == "visual" else "rank-fusion",
                    "evidence": [],
                }
            result = results[key]
            result["score"] += match["score"] if mode == "visual" else 1 / (FUSION_SMOOTHING + rank)
            result["evidence"].append(evidence)
    return sorted(results.values(), key=lambda result: (
        -result["score"], -len(result["evidence"]), result["path"], result["page"] or 0,
    ))[:top_k]


def select_paths(folder: Path, mode: str, limit: int) -> list:
    extensions = EXTENSIONS if mode == "visual" else EXTENSIONS | {".pdf"}
    supported = [path for path in sorted(folder.iterdir())
                 if path.is_file() and path.suffix.lower() in extensions]
    event("candidate_selection", supported=len(supported), selected=min(len(supported), limit),
          beyond_limit=max(0, len(supported) - limit))
    return supported[:limit]


@observed_search
def search_files(folder: Path, query: str, mode: str = "hybrid", ocr: bool = False,
                 limit: int = 10, top_k: int = 5, cache=None,
                 download: bool = False, encoder=None,
                 min_score: float = DEFAULT_MIN_SCORE) -> list:
    folder = folder.expanduser().resolve()
    if not folder.is_dir():
        raise ValueError(f"Not a folder: {folder}")
    if mode not in {"text", "visual", "hybrid"}:
        raise ValueError("Mode must be text, visual, or hybrid")
    if not normalize_text(query) or limit < 1 or top_k < 1:
        raise ValueError("Query must not be blank; limit and top_k must be positive")
    filter_visual_matches([], min_score)
    event("search_settings", mode=mode, ocr=ocr, cache_enabled=cache is not None,
          limit=limit, top_k=top_k, cutoff=min_score, query_characters=len(query),
          filename_search=False, text_matching="literal_phrase")
    if mode == "visual" and ocr:
        raise ValueError("--ocr is for text and hybrid modes")
    if mode == "text" and download:
        raise ValueError("--download-model is for visual and hybrid modes")
    paths = select_paths(folder, mode, limit)
    if not paths:
        raise ValueError("No supported files in the selected folder")
    count("selected_files", len(paths))
    event("files_selected", count=len(paths), images=sum(path.suffix.lower() in EXTENSIONS for path in paths),
          pdfs=sum(path.suffix.lower() == ".pdf" for path in paths))
    print(f"Scanning {len(paths)} candidate file(s); mode={mode}. These are not result counts.")
    text_matches = []
    visual_matches = []
    readable = False
    if mode in {"text", "hybrid"}:
        if ocr:
            check_ocr_available()
        else:
            print("Image text is excluded; add --ocr to recognize it.")
        with stage("text_index"):
            records = read_folder(folder, len(paths), ocr, cache, paths=paths, show_summaries=False)
        readable = bool(records)
        with stage("text_query"):
            text_matches = search_text(records, query)
        pdf_matches = sum(match["page"] is not None for match in text_matches)
        count("text_matches", len(text_matches))
        event("text_matches", total=len(text_matches), pdf_pages=pdf_matches,
              ocr_images=len(text_matches) - pdf_matches, filename_search=False)
        print(f"Text branch: {pdf_matches} PDF page(s), {len(text_matches) - pdf_matches} OCR image(s) matched the literal phrase. Filenames are not searched.")
    if mode in {"visual", "hybrid"}:
        image_paths = [path for path in paths if path.suffix.lower() in EXTENSIONS]
        if image_paths:
            reused_instance = encoder is not None
            if encoder is None:
                print("Loading local CLIP model...", flush=True)
                with stage("model_load"):
                    encoder = ClipEncoder(download=download)
            event("model_ready", reused_instance=reused_instance,
                  model_id=MODEL_ID, model_revision=MODEL_REVISION)
            with stage("visual_index"):
                vectors = collect_embeddings(folder, encoder, len(image_paths), cache, paths=image_paths)
            readable = readable or bool(vectors)
            if vectors:
                # Fuse all candidates before applying the final result limit.
                with stage("query_embedding"):
                    query_vector = encoder.encode_text(query)
                with stage("visual_ranking"):
                    ranked = rank_images(vectors, query_vector, len(vectors))
                visual_matches = filter_visual_matches(ranked, min_score)
                print(f"Visual cutoff {min_score:g}: kept {len(visual_matches)} of {len(ranked)} candidate image(s).")
                print("Visual results are CLIP suggestions; they do not mean the query words appear in the image.")
        else:
            print("No images selected for the visual branch; searching PDF text only.")
    if not readable:
        raise ValueError("No selected files could be read")
    with stage("fusion"):
        results = fuse_results(text_matches, visual_matches, top_k, mode)
    count("results_returned", len(results))
    event("search_results", returned=len(results), text_candidates=len(text_matches),
          visual_candidates=len(visual_matches),
          score_kind={"hybrid": "rank-fusion", "visual": "cosine", "text": "exact-match"}[mode])
    for rank, result in enumerate(results, start=1):
        event("result_ranked", level=logging.DEBUG, file_id=file_id(result["path"]),
              rank=rank, page=result["page"], score=result["score"], score_kind=result["score_kind"],
              methods=[item["method"] for item in result["evidence"]])
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--query", required=True)
    parser.add_argument("--mode", choices=["text", "visual", "hybrid"], default="hybrid")
    parser.add_argument("--ocr", action="store_true")
    parser.add_argument("--cache", action="store_true")
    parser.add_argument("--download-model", action="store_true")
    parser.add_argument("--limit", type=int, default=10, help="Maximum candidate files, shared across branches")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--min-score", type=float, default=DEFAULT_MIN_SCORE,
                        help="Minimum visual cosine before fusion (default: 0.25); does not filter exact text matches")
    parser.add_argument("--debug", action="store_true", help="Include per-file cache and score decisions in local logs")
    parser.add_argument("--no-log", action="store_true", help="Disable persistent local logs")
    args = parser.parse_args()
    cache_path = CACHE_PATH if args.cache else None
    try:
        configure_logging(enabled=not args.no_log, debug=args.debug)
        with run_context("search_files") as run_id, open_cache(cache_path) as cache:
            print(f"Run ID: {run_id}")
            results = search_files(
                args.folder, args.query, mode=args.mode, ocr=args.ocr,
                limit=args.limit, top_k=args.top_k, cache=cache,
                download=args.download_model, min_score=args.min_score,
            )
    except (ValueError, RuntimeError, ImportError, OSError, sqlite3.Error) as error:
        parser.exit(1, f"Search failed: {error}\n")
    print("Results (scores are ranking signals, not probabilities):")
    labels = {"pdf-text": "literal PDF text match", "image-ocr": "literal OCR text match",
              "clip-visual": "CLIP visual suggestion"}
    for number, result in enumerate(results, start=1):
        methods = ", ".join(labels[item["method"]] for item in result["evidence"])
        location = f"page {result['page']}" if result["page"] is not None else "image"
        print(f"  {number}. {result['path']} — {location}")
        print(f"     {result['score_kind']}={result['score']:.6f}; evidence: {methods}")
    print(f"Found {len(results)} result(s).")


if __name__ == "__main__":
    main()
