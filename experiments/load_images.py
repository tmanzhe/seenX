"""Inspect images and PDFs without modifying the original files."""

import argparse
from pathlib import Path
import sqlite3

from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader
from pypdf.errors import PyPdfError

from image_ocr import check_ocr_available, extract_image_text
from record_cache import get_record, open_cache, reader_key, save_record


def inspect_image(path: Path, ocr: bool = False) -> dict:
    with Image.open(path) as source:
        source.load()
        width, height = source.size
        record = {
            "path": str(path),
            "kind": "image",
            "format": source.format,
            "width": width,
            "height": height,
        }
        if ocr:
            try:
                record["text"] = extract_image_text(source)
                record["text_method"] = "apple-vision-ocr"
            except RuntimeError as error:
                record["ocr_error"] = str(error)
        return record


def inspect_pdf(path: Path) -> dict:
    with path.open("rb") as stream:
        reader = PdfReader(stream)
        if reader.is_encrypted:
            raise ValueError("Encrypted PDFs are not supported yet")
        pages = []
        for number, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            pages.append({"number": number, "text": text})
        return {"path": str(path), "kind": "pdf", "pages": pages}


def print_summary(record: dict) -> None:
    """Display metadata only; keep extracted document text out of the terminal."""
    name = Path(record["path"]).name
    if record["kind"] == "image":
        print(f"{name}: {record['width']} × {record['height']} ({record['format']})")
        if "ocr_error" in record:
            print(f"  OCR failed: {record['ocr_error']}")
        elif "text" in record:
            print(f"  OCR: {len(record['text'])} recognized character(s)")
    elif record["kind"] == "pdf":
        print(f"{name}: {len(record['pages'])} page(s) (PDF)")
        for page in record["pages"]:
            number = page["number"]
            text = page["text"]
            if text:
                print(f"  Page {number}: {len(text)} extracted text character(s)")
            else:
                print(f"  Page {number}: no text extracted; OCR may be needed")


def normalize_text(text: str) -> str:
    """Ignore capitalization and differences in whitespace when matching."""
    return " ".join(text.casefold().split())


def search_text(records: list, query: str) -> list:
    phrase = normalize_text(query)
    if not phrase:
        raise ValueError("Search phrase must contain non-whitespace characters")
    matches = []
    for record in records:
        if record["kind"] == "image":
            if phrase in normalize_text(record.get("text", "")):
                matches.append({"path": record["path"], "page": None})
        elif record["kind"] == "pdf":
            for page in record["pages"]:
                if phrase in normalize_text(page["text"]):
                    matches.append({"path": record["path"], "page": page["number"]})
    return matches


def read_folder(folder: Path, limit: int, ocr: bool, cache=None, refresh: bool = False) -> list:
    records = []
    reused = 0
    extensions = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
    # Sorting makes repeated runs process the same files in the same order.
    for path in sorted(folder.iterdir()):
        suffix = path.suffix.lower()
        if not path.is_file() or (suffix not in extensions and suffix != ".pdf"):
            continue
        try:
            state = path.stat()
            key = reader_key(path, ocr) if cache is not None else ""
            record = None if refresh else get_record(cache, path, key, state)
            if record is not None:
                reused += 1
            else:
                if suffix == ".pdf":
                    record = inspect_pdf(path)
                else:
                    record = inspect_image(path, ocr=ocr)
                after = path.stat()
                if (state.st_mtime_ns, state.st_size) != (after.st_mtime_ns, after.st_size):
                    raise OSError("File changed during reading; retry on the next run")
                save_record(cache, path, key, state, record)
            records.append(record)
            print_summary(record)
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError,
                PyPdfError, ValueError, NotImplementedError) as error:
            print(f"Skipped {path.name}: {error}")
        if len(records) >= limit:
            break
    if cache is not None:
        print(f"Cache: reused {reused} of {len(records)} loaded file(s).")
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path, help="Folder containing images and PDFs")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--query", help="Phrase to search for in extracted text")
    parser.add_argument("--ocr", action="store_true", help="Recognize image text locally (macOS)")
    parser.add_argument("--cache", action="store_true", help="Save and reuse extracted records locally")
    parser.add_argument("--refresh", action="store_true", help="Reread files and replace cached records (requires --cache)")
    args = parser.parse_args()
    folder = args.folder.expanduser().resolve()
    if not folder.is_dir():
        parser.error(f"Not a folder: {folder}")
    if args.limit < 1:
        parser.error("--limit must be positive")
    if args.refresh and not args.cache:
        parser.error("--refresh requires --cache")
    if args.query is not None and not normalize_text(args.query):
        parser.error("--query must contain non-whitespace characters")
    if args.ocr:
        try:
            check_ocr_available()
        except RuntimeError as error:
            parser.error(str(error))
    cache_path = Path(__file__).resolve().parent / ".cache" / "records.sqlite3" if args.cache else None
    try:
        with open_cache(cache_path) as cache:
            records = read_folder(folder, args.limit, args.ocr, cache, args.refresh)
    except (sqlite3.Error, OSError) as error:
        parser.error(f"Could not read folder or cache: {error}")

    print(f"Loaded {len(records)} file(s).")
    if not records:
        parser.exit(1, "No supported, readable files found. Try PNG, JPEG, or PDF files.\n")
    if args.query is not None:
        matches = search_text(records, args.query)
        if not args.ocr:
            print("PDF text search (use --ocr to also search image text):")
        else:
            print("PDF and image text search (scanned PDF OCR is not implemented):")
        for match in matches:
            location = f"page {match['page']}" if match["page"] is not None else "image"
            print(f"  {match['path']} — {location}")
        print(f"Found {len(matches)} match(es).")


if __name__ == "__main__":
    main()
