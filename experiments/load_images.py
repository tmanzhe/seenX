"""Inspect images and PDFs without modifying the original files."""

import argparse
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader
from pypdf.errors import PyPdfError


def inspect_image(path: Path) -> None:
    with Image.open(path) as source:
        source.load()
        width, height = source.size
        print(f"{path.name}: {width} × {height} ({source.format})")


def inspect_pdf(path: Path) -> None:
    with path.open("rb") as stream:
        reader = PdfReader(stream)
        if reader.is_encrypted:
            raise ValueError("Encrypted PDFs are not supported yet")
        print(f"{path.name}: {len(reader.pages)} page(s) (PDF)")
        for number, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                print(f"  Page {number}: {len(text)} extracted text character(s)")
            else:
                print(f"  Page {number}: no text extracted; OCR may be needed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path, help="Folder containing images and PDFs")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    folder = args.folder.expanduser().resolve()
    if not folder.is_dir():
        parser.error(f"Not a folder: {folder}")
    if args.limit < 1:
        parser.error("--limit must be positive")

    loaded = 0
    extensions = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
    # Sorting makes repeated runs process the same files in the same order.
    for path in sorted(folder.iterdir()):
        suffix = path.suffix.lower()
        if not path.is_file() or (suffix not in extensions and suffix != ".pdf"):
            continue
        try:
            if suffix == ".pdf":
                inspect_pdf(path)
            elif suffix in extensions:
                inspect_image(path)
            loaded += 1
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError,
                PyPdfError, ValueError, NotImplementedError) as error:
            print(f"Skipped {path.name}: {error}")
        if loaded >= args.limit:
            break

    print(f"Loaded {loaded} file(s).")
    if not loaded:
        parser.exit(1, "No supported, readable files found. Try PNG, JPEG, or PDF files.\n")


if __name__ == "__main__":
    main()
