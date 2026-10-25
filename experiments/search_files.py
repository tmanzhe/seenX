"""Search one local collection with text, visual similarity, or both."""

import argparse
from pathlib import Path
import sqlite3

from image_ocr import check_ocr_available
from load_images import normalize_text, read_folder, search_text
from record_cache import open_cache
from visual_search import ClipEncoder, EXTENSIONS, collect_embeddings, rank_images

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
    return [path for path in sorted(folder.iterdir())
            if path.is_file() and path.suffix.lower() in extensions][:limit]


def search_files(folder: Path, query: str, mode: str = "hybrid", ocr: bool = False,
                 limit: int = 10, top_k: int = 5, cache=None,
                 download: bool = False, encoder=None) -> list:
    folder = folder.expanduser().resolve()
    if not folder.is_dir():
        raise ValueError(f"Not a folder: {folder}")
    if mode not in {"text", "visual", "hybrid"}:
        raise ValueError("Mode must be text, visual, or hybrid")
    if not normalize_text(query) or limit < 1 or top_k < 1:
        raise ValueError("Query must not be blank; limit and top_k must be positive")
    if mode == "visual" and ocr:
        raise ValueError("--ocr is for text and hybrid modes")
    if mode == "text" and download:
        raise ValueError("--download-model is for visual and hybrid modes")
    paths = select_paths(folder, mode, limit)
    if not paths:
        raise ValueError("No supported files in the selected folder")
    print(f"Mode: {mode}; selected {len(paths)} file(s).")
    text_matches = []
    visual_matches = []
    readable = False
    if mode in {"text", "hybrid"}:
        if ocr:
            check_ocr_available()
        else:
            print("Image text is excluded; add --ocr to recognize it.")
        records = read_folder(folder, len(paths), ocr, cache, paths=paths)
        readable = bool(records)
        text_matches = search_text(records, query)
    if mode in {"visual", "hybrid"}:
        image_paths = [path for path in paths if path.suffix.lower() in EXTENSIONS]
        if image_paths:
            if encoder is None:
                print("Loading local CLIP model...", flush=True)
                encoder = ClipEncoder(download=download)
            vectors = collect_embeddings(folder, encoder, len(image_paths), cache, paths=image_paths)
            readable = readable or bool(vectors)
            if vectors:
                # Fuse all candidates before applying the final result limit.
                visual_matches = rank_images(vectors, encoder.encode_text(query), len(vectors))
        else:
            print("No images selected for the visual branch; searching PDF text only.")
    if not readable:
        raise ValueError("No selected files could be read")
    return fuse_results(text_matches, visual_matches, top_k, mode)


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
    args = parser.parse_args()
    cache_path = Path(__file__).resolve().parent / ".cache" / "records.sqlite3" if args.cache else None
    try:
        with open_cache(cache_path) as cache:
            results = search_files(
                args.folder, args.query, mode=args.mode, ocr=args.ocr,
                limit=args.limit, top_k=args.top_k, cache=cache,
                download=args.download_model,
            )
    except (ValueError, RuntimeError, ImportError, OSError, sqlite3.Error) as error:
        parser.exit(1, f"Search failed: {error}\n")
    print("Results (scores are ranking signals, not probabilities):")
    for number, result in enumerate(results, start=1):
        methods = ", ".join(item["method"] for item in result["evidence"])
        location = f"page {result['page']}" if result["page"] is not None else "image"
        print(f"  {number}. {result['path']} — {location}")
        print(f"     {result['score_kind']}={result['score']:.6f}; evidence: {methods}")
    print(f"Found {len(results)} result(s).")


if __name__ == "__main__":
    main()
