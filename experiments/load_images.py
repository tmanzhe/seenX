"""Inspect images and PDFs without modifying the original files."""

import argparse
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader
from pypdf.errors import PyPdfError


def inspect_image(path: Path) -> dict:
    with Image.open(path) as source:
        source.load()
        width, height = source.size
        return {
            "path": str(path),
            "kind": "image",
            "format": source.format,
            "width": width,
            "height": height,
        }


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


def search_pdf_text(records: list, query: str) -> list:
    phrase = normalize_text(query)
    if not phrase:
        raise ValueError("Search phrase must contain non-whitespace characters")
    matches = []
    for record in records:
        if record["kind"] != "pdf":
            continue
        for page in record["pages"]:
            if phrase in normalize_text(page["text"]):
                matches.append({"path": record["path"], "page": page["number"]})
    return matches


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path, help="Folder containing images and PDFs")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--query", help="Phrase to search for in extracted PDF text")
    args = parser.parse_args()
    folder = args.folder.expanduser().resolve()
    if not folder.is_dir():
        parser.error(f"Not a folder: {folder}")
    if args.limit < 1:
        parser.error("--limit must be positive")
    if args.query is not None and not normalize_text(args.query):
        parser.error("--query must contain non-whitespace characters")

    records = []
    extensions = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
    # Sorting makes repeated runs process the same files in the same order.
    for path in sorted(folder.iterdir()):
        suffix = path.suffix.lower()
        if not path.is_file() or (suffix not in extensions and suffix != ".pdf"):
            continue
        try:
            if suffix == ".pdf":
                record = inspect_pdf(path)
            elif suffix in extensions:
                record = inspect_image(path)
            records.append(record)
            print_summary(record)
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError,
                PyPdfError, ValueError, NotImplementedError) as error:
            print(f"Skipped {path.name}: {error}")
        if len(records) >= args.limit:
            break

    print(f"Loaded {len(records)} file(s).")
    if not records:
        parser.exit(1, "No supported, readable files found. Try PNG, JPEG, or PDF files.\n")
    if args.query is not None:
        matches = search_pdf_text(records, args.query)
        print("PDF text search (images are not searched yet):")
        for match in matches:
            print(f"  {match['path']} — page {match['page']}")
        print(f"Found {len(matches)} matching page(s).")


if __name__ == "__main__":
    main()
