# Learning Python by building seenX

We're building a local file-search prototype, one useful piece at a time. The idea is to find a screenshot, photo, or document using something you remember about it. Python lets us try the pieces and understand the results before deciding what belongs in the Rust desktop engine.

Right now we can open images and PDFs, collect information about them, and display a summary. We haven't added OCR, embeddings, AI models, a database, or a Python web server. The Next.js website is a separate project under `apps/web`; this script isn't connected to it.

## Get it running

These commands start at the repository root. You need Python 3.13 or newer installed.

```sh
cd experiments
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
mkdir -p ../practice-images
python load_images.py ../practice-images
```

Put a few of your own JPEGs, PNGs, or PDFs into `practice-images` before the last command. You can also pass an existing folder:

```sh
python load_images.py "/path/to/your/folder" --limit 5
```

Quotes keep a path containing spaces together as one argument. `--limit 5` means stop after five successfully read files, not five PDF pages. The default is ten files. We only inspect the immediate folder, not subfolders.

On later visits, you only need to activate the environment and run the script. Run `deactivate` to leave the environment. For command help, run `python load_images.py --help`.

### What did those setup commands do?

- `cd experiments` changes the terminal's current directory. Relative paths are interpreted from that directory.
- `python3 -m venv .venv` asks Python to run its built-in `venv` module and create an isolated environment in `.venv`.
- `source .venv/bin/activate` tells this terminal to use that environment's Python and packages.
- `python -m pip install -e .` installs the dependencies recorded in `pyproject.toml`. The dot means the current directory; `-e` means an editable project installation.
- `mkdir -p ../practice-images` creates our input folder if it doesn't already exist. `..` means the parent directory.

`pyproject.toml` also names setuptools as the installation tool and explicitly identifies `load_images` as our Python module. That prevents the installer from mistaking local data folders for code packages. You don't need to learn packaging internals to run the script.

A virtual environment isn't a virtual machine. Python still runs directly on your Mac. It just keeps this project's packages separate from other projects. `bin` is a directory of executable programs; `.venv/bin/python` is the interpreter that executes our script. You don't write application code inside it.

Check which interpreter you're using:

```sh
python -c "import sys; print(sys.executable)"
```

The printed path should point inside this project's `.venv`. From the repository root, you can skip activation by calling it explicitly:

```sh
experiments/.venv/bin/python experiments/load_images.py practice-images
```

## Where things live

| Location | What it's for |
| --- | --- |
| `load_images.py` | The Python script. Despite the name, it now supports PDFs too. |
| `pyproject.toml` | The Python version requirement and dependencies. |
| `.venv/` | The interpreter and installed packages. Generated locally and ignored by Git. |
| `../practice-images/` | Your original files. Ignored by Git. |
| `data/`, `outputs/` | Empty leftovers from an early smoke check. The script doesn't use them. |

The script doesn't create images, thumbnails, or a manifest. Your originals are opened for reading. Extracted PDF text stays in memory for this run and isn't saved or printed. Personal files, model downloads, and future experiment outputs should stay out of Git.

## How we built this, and why

### 1. Start by opening a real image

Before trying search, we needed to know we could read the files. We installed **Pillow**, a library for opening and processing images:

```python
from PIL import Image
```

Pillow is the package's name; `PIL` is its historical import name. `Image` is a module, not an AI model. It can decode a JPEG into pixels, but it doesn't know whether those pixels show a mountain or a laptop.

```python
with Image.open(path) as source:
    source.load()
    width, height = source.size
```

`Image.open(path)` identifies and opens the file. `source.load()` decodes its pixels, so damaged data can fail here. `source.size` gives two values, which we assign to `width` and `height`. The `with` block closes the file when we're finished, including when an error occurs. Dimensions describe the stored pixels before any rotation metadata is applied.

We initially made a generated test image and thumbnails. We removed both because they weren't needed to learn file reading. We now use our own existing files.

### 2. Give PDFs their own reader

A PDF can contain multiple pages, text, images, and drawings. Treating every PDF as an image would throw away useful existing text. We added **pypdf** to extract that text directly:

```python
with path.open("rb") as stream:
    reader = PdfReader(stream)
```

`"rb"` means read in binary mode: read the file's bytes rather than interpreting it as a plain text file. `PdfReader` interprets the PDF structure for us.

For each page, we use:

```python
text = (page.extract_text() or "").strip()
```

`extract_text()` returns text when it can. `or ""` gives us an empty string if the result is missing or empty. `.strip()` removes whitespace from the ends. This doesn't recognize words in scanned images: that's a separate step called **OCR**, or optical character recognition. No extracted text means OCR may be needed; it doesn't prove the page is blank.

### 3. Return data that other code can use

Printing a width is useful to a person, but search code needs the value itself. We changed the reader functions to return **dictionaries**:

```python
return {
    "kind": "image",
    "width": width,
    "height": height,
}
```

This example omits a few fields for clarity. A dictionary stores values under named keys. `record["width"]` retrieves the value stored under `"width"`. `return` sends the dictionary back to the code that called the function and ends that function call.

```python
record = inspect_image(path)
records.append(record)
```

`record` holds one file's information. `records` is a **list**, an ordered collection. Its `.append()` method adds one item to the end. A PDF record contains a list of page dictionaries, each holding a page number and extracted text. Keeping the page number means search results can eventually point you to a specific page.

`print_summary(record)` handles the display separately. We can change the terminal presentation without changing how files are read. The readers themselves don't print document contents.

The current flow is:

```text
terminal arguments → folder → choose reader → return dictionary
                                           → append to list → print summary
```

The list only lives during the run. There is no persistent index yet, and PDF text consumes memory while retained. This is a small-folder experiment.

## Reading the rest of the script

`main()` coordinates the work. Here's what its building blocks mean:

| Code or term | What it does here |
| --- | --- |
| `def inspect_image(path: Path) -> dict:` | Defines a function with a `path` parameter. The type hints describe the expected input and return type; they don't enforce them at runtime. |
| `argparse.ArgumentParser(...)` | Creates a command-line parser: an object that interprets the arguments typed after the script name. |
| `parser.add_argument(...)` | Defines an accepted argument. `folder` is required; `--limit` is optional. |
| `args = parser.parse_args()` | Reads the arguments and exposes values such as `args.folder`. |
| `folder.expanduser().resolve()` | Expands `~` and produces an absolute path. |
| `if` / `elif` | Chooses PDF or image handling based on the filename extension. Opening the file then checks whether that reader can read it. |
| `for path in sorted(folder.iterdir())` | Visits the immediate folder's entries in a repeatable filename order. |
| `continue` / `break` | Skips an unsupported entry / stops after reaching the limit. |
| `enumerate(reader.pages, start=1)` | Supplies each PDF page together with its human-readable number. |
| `try` / `except` | Reports known reading failures and continues with other files. |
| `len(records)` | Counts successfully collected file records. |
| `f"Loaded {len(records)} file(s)."` | An f-string: inserts an expression's value into text. |
| `if __name__ == "__main__":` | Calls `main()` when this file runs directly, but not when another script imports it. |

A **function call** uses parentheses: `inspect_image(path)`. A **method** is a function accessed through an object: `records.append(record)`. An **attribute** provides information without a call: `source.size`. A **parameter** is the input name in the function definition; an **argument** is the value supplied when calling it.

## What to expect, and current limits

The terminal prints image dimensions and formats, PDF page counts, and extracted text character counts for each page. It doesn't print the PDF text itself. It finishes with a successful-file count. As an initial check, we read eight personal images and one two-page PDF; both PDF pages had extractable text.

Supported images are JPEG, PNG, WebP, BMP, and TIFF. HEIC isn't supported yet. Unsupported extensions are skipped. Encrypted PDFs and known reading errors are reported and skipped. If no readable files are found, the command exits with an error. The extension is a routing hint, not a universal file-type detector, and successful text extraction doesn't guarantee perfect reading order or table structure.

## Topics to learn alongside the code

Start with **variables**, **strings and integers**, **functions and arguments**, **indentation**, **conditions**, and **loops**. You don't need to master everything before continuing.

For this latest step, search for:

- `Python return values`: how a reader sends data back to its caller.
- `Python dictionaries keys values`: how we name fields in a file record.
- `Python lists append`: how we collect multiple records.
- `Python nested dictionaries and lists`: how PDF pages belong to a document record.

Other concepts already used are `Python pathlib`, `Python argparse beginner`, `Python with statement`, `Python try except`, `Python enumerate`, `Python f strings`, and `Python type hints basics`.

## What comes next

Next we'll search the extracted PDF text with a phrase and return matching filenames and page numbers. That gives us a small working search before adding AI. Then we can add OCR for screenshot text and image embeddings for visual descriptions. Each feature gets its own verification and Git commit, separate from frontend changes.

Later, we'll compare keyword and semantic retrieval on labeled queries, and test whether relationships such as receipts belonging to trips improve results. Models may propose relationships; evidence and user confirmation need to stay distinguishable. We will measure useful behavior before moving it into the Rust engine. Python is our development reference, not a required runtime for the intended desktop release.

See the [project overview](../README.md), [architecture](../docs/architecture.md), and [implementation plan](../plan.md).
