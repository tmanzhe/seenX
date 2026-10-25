# Learning Python by building seenX

We're building a local file-search prototype, one useful piece at a time. The idea is to find a screenshot, photo, or document using something you remember about it. Python lets us try the pieces and understand the results before deciding what belongs in the Rust desktop engine.

Right now we can open images and PDFs, recognize image text with optional local OCR on macOS, and search both kinds of text. We haven't added embeddings, a database, or a Python web server. OCR uses Apple's pretrained text-recognition system; we aren't training a model. The Next.js website is a separate project under `apps/web`; this script isn't connected to it.

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
| `image_ocr.py` | The small adapter between Python and Apple's Vision OCR framework. |
| `test_search.py`, `test_ocr.py` | Repeatable checks for matching and OCR behavior. |
| `pyproject.toml` | The Python version requirement and dependencies. |
| `.venv/` | The interpreter and installed packages. Generated locally and ignored by Git. |
| `../practice-images/` | Your original files. Ignored by Git. |
| `data/`, `outputs/` | Empty leftovers from an early smoke check. The script doesn't use them. |

The script doesn't save converted images, thumbnails, or a manifest. Your originals are opened for reading. Extracted text stays in memory for this run and isn't saved or printed. Personal files, model downloads, and future experiment outputs should stay out of Git.

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

### 4. Search the PDF text

Now we can do something useful with those records. From `experiments`, with the environment activated:

```sh
python load_images.py ../practice-images --query "a phrase from your PDF"
```

Replace the quoted phrase with words you know appear in one of your documents. You'll see the usual file summaries followed by matching file paths and page numbers. We don't print document excerpts. A page appears once even if the phrase occurs several times. Zero matches is a normal result; an empty or whitespace-only query is an input error.

We first built this for PDFs, then renamed the function to `search_text(records, query)` when we added image OCR. It reads the records we already collected. Images without recognized text have nothing to match. For each PDF page it asks:

```python
if phrase in normalize_text(page["text"]):
    matches.append({"path": record["path"], "page": page["number"]})
```

`in` checks whether one string occurs inside another. This is a substring search: `train` also matches `trains`. We return a list of dictionaries, so the terminal is just one way to display results. We keep the file path and page number so you can find the source.

Before comparing, we normalize both the query and the page text:

```python
return " ".join(text.casefold().split())
```

Read that from the inside out:

1. `.casefold()` makes text suitable for comparisons that ignore capitalization, including Unicode cases beyond English.
2. `.split()` with no arguments breaks the string into a list of pieces at whitespace. Repeated spaces, tabs, and line breaks become separators.
3. `" ".join(...)` puts those pieces back together with one space between them.

That lets `TRAIN BOOKING` match `Train` followed by a line break and `booking`. We don't remove punctuation, fix OCR mistakes, match synonyms, rank results, or join phrases across page boundaries. PDF extraction can also produce unexpected reading order. These are useful limits to understand before adding more sophisticated search.

Every run reads the files again. `--limit` still applies to the combined image/PDF collection before searching, so use a larger limit if a desired PDF is later in filename order. Without `--ocr`, the command reminds you that only PDF text is searched.

We test the matching behavior with invented text dictionaries, not copies of personal documents or generated images:

```sh
python -m unittest discover -s . -p 'test_*.py' -v
```

The tests check capitalization, whitespace, Unicode matching, correct page references, multiple documents, missing matches, empty pages, and blank queries. They also check that a repeated phrase only returns its page once.

### 5. Read words inside images with OCR

Pillow gives us pixels. To turn visible words into a Python string, we need optical character recognition. We chose **Apple Vision** because this project targets macOS and we can use the operating system's OCR locally. **PyObjC** is the bridge that lets Python call Apple's Objective-C APIs. It isn't an OCR engine itself.

On a Mac, run these commands from `experiments`, with the environment activated:

```sh
python -m pip install -e ".[ocr]"
python load_images.py ../practice-images --ocr
python load_images.py ../practice-images --ocr --query "words visible in your image"
```

`[ocr]` selects the optional dependency group in `pyproject.toml`. Plain file reading and PDF text search don't require it. On other operating systems, `--ocr` exits with a clear message; we haven't added a portable OCR backend yet.

`--ocr` is a boolean flag. In argparse, `action="store_true"` means its value is `True` when supplied and `False` when omitted. We pass that value into `inspect_image(path, ocr=args.ocr)`. The function's `ocr=False` default keeps existing calls working without recognition.

We put the macOS-specific code in `image_ocr.py` so the folder-reading and search code don't need to know how Vision works. Its imports happen when OCR is requested, so missing optional packages don't stop the basic reader.

The adapter does this:

1. Uses Pillow to apply rotation metadata and prepare RGB pixels. It encodes a PNG into `BytesIO`, an in-memory byte buffer. This is an internal format handoff, not another saved image or a thumbnail.
2. Wraps those bytes as Apple's `NSData` and creates a `VNRecognizeTextRequest` in accurate mode, with English recognition and language correction.
3. Passes the request to a `VNImageRequestHandler`. The long method names with underscores come from the Objective-C API through PyObjC; they aren't naming patterns you need for ordinary Python functions. We use a native empty `NSDictionary` for handler options because passing a Python dictionary failed in our real-image check.
4. Takes the top text candidate from each recognized region and joins those strings with line breaks.

`objc.autorelease_pool()` bounds the lifetime of temporary native objects. Think of it as cleanup for Apple's objects during each image; you don't need to learn Objective-C memory management to use this adapter.

The image record gets `text` and `text_method: "apple-vision-ocr"`. The method label preserves where the words came from. No recognized text is an empty string. A recognition failure instead gets an `ocr_error` message, while keeping the readable image metadata. Missing dependencies are caught before scanning the folder.

Search uses the same normalization and substring check for OCR text and PDF text. An image result has `page: None`, meaning a page number doesn't apply. The terminal prints its path followed by `image`; PDF results still include page numbers. It prints character counts rather than recognized contents.

All recognition happens locally; this code makes no upload or cloud API call. It uses the OCR supplied by the installed OS, so results can vary across OS versions. A trial on our eight practice images recognized text in two of them. That checks that the pipeline runs, not that every word is correct. Blurry text, unusual layouts, handwriting, and non-English content can fail. Language selection, confidence scoring, bounding boxes, and OCR for scanned PDF pages are still future work. For multi-frame image files, only the first frame is processed.

For reference: [Apple's text-recognition request](https://developer.apple.com/documentation/vision/vnrecognizetextrequest) and [PyObjC framework wrappers](https://pyobjc.readthedocs.io/en/latest/notes/framework-wrappers.html).

The tests include mixed image/PDF search and clear errors for unsupported platforms and missing dependencies. An optional local-image check mocks recognition to distinguish disabled OCR, no text, and a recognition error. It skips if there isn't a local practice JPEG. No personal files are committed.

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

The terminal prints image dimensions and formats, optional OCR character counts, PDF page counts, and extracted text character counts for each page. It doesn't print extracted contents. It finishes with a loaded-file count and, when queried, a match count. A loaded file isn't a guarantee of successful OCR; check its OCR status. As an initial check, we read eight personal images and one two-page PDF; both PDF pages had extractable text.

Supported images are JPEG, PNG, WebP, BMP, and TIFF. HEIC isn't supported yet. Unsupported extensions are skipped. Encrypted PDFs and known reading errors are reported and skipped. If no readable files are found, the command exits with an error. The extension is a routing hint, not a universal file-type detector, and successful text extraction doesn't guarantee perfect reading order or table structure.

## Topics to learn alongside the code

Start with **variables**, **strings and integers**, **functions and arguments**, **indentation**, **conditions**, and **loops**. You don't need to master everything before continuing.

For this latest step, search for:

- `Python boolean flags argparse store_true`: how `--ocr` turns recognition on.
- `Python default parameter values`: why `ocr=False` makes recognition optional.
- `Python modules imports`: why we moved the adapter into its own file.
- `Python dictionary get default`: how `record.get("text", "")` handles images without OCR text.
- `Python None`: why image results don't have a page number.
- `Python BytesIO`: how we pass encoded pixels in memory.
- `Python unittest mock patch`: how tests simulate OCR failures without making images.

The search step introduced:

- `Python string in substring`: how we check whether a page contains the phrase.
- `Python str casefold`: how we ignore capitalization.
- `Python split join whitespace`: how we match across line breaks.
- `Python unittest basics`: how we check behavior with repeatable examples.

The previous step introduced:

- `Python return values`: how a reader sends data back to its caller.
- `Python dictionaries keys values`: how we name fields in a file record.
- `Python lists append`: how we collect multiple records.
- `Python nested dictionaries and lists`: how PDF pages belong to a document record.

Other concepts already used are `Python pathlib`, `Python argparse beginner`, `Python with statement`, `Python try except`, `Python enumerate`, `Python f strings`, and `Python type hints basics`.

## What comes next

We now have PDF and image text search. Next we'll measure which queries it handles and where it fails before adding image embeddings for visual descriptions that don't depend on visible words. OCR for scanned PDFs is another separate step. Each feature gets its own verification and Git commit, separate from frontend changes.

Later, we'll compare keyword and semantic retrieval on labeled queries, and test whether relationships such as receipts belonging to trips improve results. Models may propose relationships; evidence and user confirmation need to stay distinguishable. We will measure useful behavior before moving it into the Rust engine. Python is our development reference, not a required runtime for the intended desktop release.

See the [project overview](../README.md), [architecture](../docs/architecture.md), and [implementation plan](../plan.md).
