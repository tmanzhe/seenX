"""Find images by visual description using a local pretrained CLIP model."""

import argparse
from importlib.metadata import version
import math
from pathlib import Path
import sqlite3
from time import perf_counter

from PIL import Image, ImageOps, UnidentifiedImageError

from record_cache import get_record, open_cache, save_record


MODEL_ID = "openai/clip-vit-base-patch32"
# Explicit safetensors conversion revision in the original model repository.
MODEL_REVISION = "c7244be81152024ce0e99ac8d2e373a8953d9f9a"
MODEL_CACHE = Path(__file__).resolve().parent.parent / "models" / "huggingface"
EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
DEFAULT_MIN_SCORE = 0.25


def filter_visual_matches(matches: list, min_score: float = DEFAULT_MIN_SCORE) -> list:
    """Reject weak similarities; this cutoff is a heuristic, not confidence."""
    if not math.isfinite(min_score) or not -1 <= min_score <= 1:
        raise ValueError("--min-score must be a finite cosine score between -1 and 1")
    return [match for match in matches if match["score"] >= min_score]


def normalize_vector(values: list) -> list:
    if not values or not all(math.isfinite(value) for value in values):
        raise ValueError("Embedding must contain finite numbers")
    length = math.sqrt(sum(value * value for value in values))
    if length == 0:
        raise ValueError("Embedding must not be a zero vector")
    return [value / length for value in values]


def rank_images(records: list, query_vector: list, top_k: int) -> list:
    if top_k < 1:
        raise ValueError("top_k must be positive")
    query = normalize_vector(query_vector)
    results = []
    for record in records:
        image = normalize_vector(record["embedding"])
        if len(image) != len(query):
            raise ValueError("Image and query embeddings have different dimensions")
        score = sum(left * right for left, right in zip(query, image))
        results.append({"path": record["path"], "score": score})
    return sorted(results, key=lambda result: (-result["score"], result["path"]))[:top_k]


class ClipEncoder:
    """Keep the matching model and its preprocessing together for a run."""

    def __init__(self, download: bool = False):
        try:
            import torch
            from transformers import CLIPModel, CLIPProcessor
        except ImportError as error:
            raise RuntimeError('Install visual support: python -m pip install -e ".[visual]"') from error
        self.torch = torch
        options = {
            "revision": MODEL_REVISION,
            "cache_dir": str(MODEL_CACHE),
            "local_files_only": not download,
        }
        self.processor = CLIPProcessor.from_pretrained(MODEL_ID, use_fast=False, **options)
        self.model = CLIPModel.from_pretrained(MODEL_ID, use_safetensors=True, **options)
        self.model.to("cpu")
        self.model.eval()
        self.cache_key = ":".join([
            "visual-v1", MODEL_ID, MODEL_REVISION, "exif-rgb-slow-processor-cpu",
            version("Pillow"), version("torch"), version("transformers"),
        ])

    def encode_image(self, source) -> list:
        image = ImageOps.exif_transpose(source).convert("RGB")
        inputs = self.processor(images=image, return_tensors="pt")
        with self.torch.inference_mode():
            features = self.model.get_image_features(**inputs)
        return normalize_vector(features[0].tolist())

    def encode_text(self, query: str) -> list:
        inputs = self.processor(
            text=[query], return_tensors="pt", padding=True, truncation=True,
            max_length=self.model.config.text_config.max_position_embeddings,
        )
        with self.torch.inference_mode():
            features = self.model.get_text_features(**inputs)
        return normalize_vector(features[0].tolist())


def collect_embeddings(folder: Path, encoder, limit: int, cache=None,
                       paths: list | None = None) -> list:
    records = []
    reused = 0
    candidates = sorted(folder.iterdir()) if paths is None else paths
    for path in candidates:
        if not path.is_file() or path.suffix.lower() not in EXTENSIONS:
            continue
        try:
            state = path.stat()
            record = get_record(cache, path, encoder.cache_key, state)
            if record is None:
                with Image.open(path) as source:
                    source.load()
                    embedding = encoder.encode_image(source)
                after = path.stat()
                if (state.st_mtime_ns, state.st_size) != (after.st_mtime_ns, after.st_size):
                    raise OSError("File changed during encoding; retry next run")
                record = {"path": str(path), "embedding": embedding}
                save_record(cache, path, encoder.cache_key, state, record)
            else:
                reused += 1
            records.append(record)
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError, ValueError) as error:
            print(f"Skipped {path.name}: {error}")
        if len(records) >= limit:
            break
    print(f"Indexed {len(records)} image(s); reused {reused} cached embedding(s).")
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--query", required=True, help="Visual description, e.g. a photo of a cat")
    parser.add_argument("--limit", type=int, default=10, help="Maximum readable images to index")
    parser.add_argument("--top-k", type=int, default=5, help="Maximum results to return")
    parser.add_argument("--min-score", type=float, default=DEFAULT_MIN_SCORE,
                        help="Minimum visual cosine similarity (default: 0.25; not a probability)")
    parser.add_argument("--cache", action="store_true", help="Save and reuse image embeddings locally")
    parser.add_argument("--download-model", action="store_true", help="Allow downloading pinned model files (otherwise offline)")
    args = parser.parse_args()
    folder = args.folder.expanduser().resolve()
    if not folder.is_dir():
        parser.error(f"Not a folder: {folder}")
    if not args.query.strip():
        parser.error("--query must contain non-whitespace characters")
    if args.limit < 1 or args.top_k < 1:
        parser.error("--limit and --top-k must be positive")
    try:
        filter_visual_matches([], args.min_score)
    except ValueError as error:
        parser.error(str(error))
    if not any(path.is_file() and path.suffix.lower() in EXTENSIONS for path in folder.iterdir()):
        parser.error("No supported image files found; PDFs are not searched by this command")

    try:
        started = perf_counter()
        print(f"Loading {MODEL_ID} at {MODEL_REVISION} on CPU...", flush=True)
        encoder = ClipEncoder(download=args.download_model)
        loaded = perf_counter()
        cache_path = Path(__file__).resolve().parent / ".cache" / "records.sqlite3" if args.cache else None
        with open_cache(cache_path) as cache:
            records = collect_embeddings(folder, encoder, args.limit, cache)
        indexed = perf_counter()
        if not records:
            parser.exit(1, "No readable images were indexed.\n")
        query_vector = encoder.encode_text(args.query)
        ranked = rank_images(records, query_vector, len(records))
        results = filter_visual_matches(ranked, args.min_score)[:args.top_k]
        searched = perf_counter()
    except (ImportError, OSError, RuntimeError, ValueError, sqlite3.Error) as error:
        parser.exit(1, f"Visual search failed: {error}\nFor a first run, install .[visual] and use --download-model.\n")

    print(f"Visual matches with cosine >= {args.min_score:g} (scores are not probabilities):")
    for number, result in enumerate(results, start=1):
        print(f"  {number}. {result['score']:.4f}  {result['path']}")
    print(f"Found {len(results)} visual match(es); --top-k is a maximum, not a target.")
    if not results:
        print("No images met the visual cutoff.")
    print(f"Seconds: model load {loaded - started:.3f}; indexing {indexed - loaded:.3f}; query {searched - indexed:.3f}")


if __name__ == "__main__":
    main()
