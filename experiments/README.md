# Learning Python by building seenX

We're building a local file-search prototype, one useful piece at a time. The idea is to find a screenshot, photo, or document using something you remember about it. Python lets us try the pieces and understand the results before deciding what belongs in the Rust desktop engine.

Right now we can read images and PDFs, recognize image text with optional local OCR, search that text, and retrieve images by visual description using CLIP embeddings. `search_files.py` brings those approaches together in one command with text, visual, and hybrid modes. An optional SQLite cache lets us reuse extracted records and image vectors between runs. We haven't added a Python web server. Both OCR and visual search use pretrained models; we aren't training them. The Next.js website is a separate project under `apps/web`; these scripts aren't connected to it.

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
| `record_cache.py` | Stores and retrieves extracted records with Python's built-in SQLite support. |
| `visual_search.py` | A separate command for matching image contents against a text description. |
| `search_files.py` | The combined search command and reusable search function. Start with step 8 to try all modes. |
| `test_search.py`, `test_ocr.py`, `test_cache.py` | Repeatable checks for matching, OCR, and cache behavior. |
| `pyproject.toml` | The Python version requirement and dependencies. |
| `.venv/` | The interpreter and installed packages. Generated locally and ignored by Git. |
| `../practice-images/` | Your original files. Ignored by Git. |
| `data/`, `outputs/` | Empty leftovers from an early smoke check. The script doesn't use them. |
| `.cache/records.sqlite3` | Optional local database created by `--cache`. Contains extracted text and paths; ignored by Git. |
| `../models/huggingface/` | Downloaded model files. Local and ignored by Git. |

The script doesn't save converted images, thumbnails, or a manifest. Your originals are opened for reading. Without `--cache`, extracted text stays in memory for this run. With `--cache`, text and file paths are saved in the local database. Extracted contents aren't printed. Personal files, cache databases, model downloads, and future experiment outputs should stay out of Git.

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

The list lives during the run, and PDF text consumes memory while retained. Step 6 adds optional persistence for the records, but search still scans the in-memory list. This is a small-folder experiment.

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

Without caching, every run reads the files again. `--limit` still applies to the combined image/PDF collection before searching, so use a larger limit if a desired PDF is later in filename order. Without `--ocr`, the command reminds you that only PDF text is searched.

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

### 6. Stop rereading unchanged files

Once OCR worked, a practical problem showed up: each new query ran recognition again. We added an optional **cache**, a saved copy of extraction results that we can reuse when the source hasn't changed.

From `experiments`, with the environment activated:

```sh
python load_images.py ../practice-images --ocr --cache --query "your phrase"
python load_images.py ../practice-images --ocr --cache --query "another phrase"
```

On the first run the database starts empty. On the next run, a line such as `Cache: reused 9 of 9 loaded file(s).` tells you extraction was skipped for those files. Without `--cache`, the command behaves as it did before and doesn't read or write the database.

We chose **SQLite** because Python includes it as the `sqlite3` module. It's a database stored in one local file, with no database server to install or run. A table is a collection of rows with named columns. Each row stores a file path, a reader identifier, the file's modification timestamp and size, and the extracted record.

The reader identifier includes our record-format version and relevant library versions. Image OCR also includes the macOS version and recognition settings. This keeps results from different extraction modes separate. Running without `--ocr` won't accidentally search text left over from an earlier OCR run. If we change our extraction code or settings, we need to update the reader identifier too.

Before reading a file, `read_folder()` asks the cache for a matching row:

```python
record = get_record(cache, path, key, state)
```

A returned dictionary is a **cache hit**. `None` is a **cache miss**, so we read the source normally. `path.stat()` provides the source's modification time and byte size. If either changes, the old row doesn't match and extraction runs again. This is a quick freshness check, not a content hash: deliberately preserving both size and timestamp can hide a change.

Inside the cache, this SQL query finds a matching record:

```sql
SELECT record FROM records
WHERE path = ? AND reader = ? AND mtime_ns = ? AND size = ?
```

SQL is the language used to ask the database for data. The `?` placeholders are filled with separately supplied values. We don't paste filenames into SQL strings. `fetchone()` gets one matching row, or returns `None`.

SQLite stores the dictionary as **JSON**, a text format for lists, dictionaries, numbers, and strings. `json.dumps(record)` serializes the Python dictionary into text. `json.loads(...)` deserializes it back into Python values. We store strings rather than `Path` objects so every record can be serialized directly.

`INSERT OR REPLACE` saves the new record for a file and reader. `commit()` makes the write persistent. `open_cache()` is a context manager built with `@contextmanager`: it opens the connection, `yield`s it to the `with` block, then closes it in `finally`, even if the run fails. With caching disabled it yields `None`, and the cache helpers do nothing.

To deliberately rerun extraction for the files in this scan:

```sh
python load_images.py ../practice-images --ocr --cache --refresh
```

`--refresh` requires `--cache`. It bypasses saved records and replaces successful results. Known OCR failures aren't saved, so failed recognition is retried rather than becoming a permanent empty result. A file whose size or timestamp changes during extraction is skipped and can be retried next time.

We still scan the selected folder on every run. A deleted file therefore won't appear in results, even if an old row remains in the database. Old rows aren't automatically purged: the database retains extracted text until you remove it. To discard all cached text, stop the script and delete `.cache/records.sqlite3` inside `experiments`; the next cached run creates it again. The database is ordinary unencrypted local storage and stays ignored by Git.

This is an extraction cache, not a database search engine. Search still uses the same Python substring matching over the loaded records, and the file limit still applies. Caching avoids repeated OCR and PDF extraction; it doesn't add ranking, folder watching, or full-text indexing. OCR dependencies are still required whenever `--ocr` is requested, even with a warm cache.

The cache tests use temporary placeholder files and invented records. They check persistence after reopening, changed file size and timestamps, reader changes, forced refresh, OCR failures, files removed from the folder, and files changing during extraction. They don't create image fixtures or commit personal data.

### 7. Find pictures by what they show

OCR can read the word "cat" in a screenshot, but a cat photo may contain no writing at all. For that we added a separate visual-search command. Keeping it separate makes it easy to compare visual retrieval with exact text matching before combining them.

From `experiments`, activate the environment and install the optional model libraries:

```sh
python -m pip install -e ".[visual]"
python visual_search.py ../practice-images --query "a photo of a laptop computer" --cache --download-model
```

The first run downloads the pinned model files from Hugging Face into `models/huggingface` at the repository root. The model weights are roughly 600 MB, in addition to the Python packages. Your images are processed locally and aren't uploaded. No generated images or thumbnails are saved.

After the download, leave off `--download-model`:

```sh
python visual_search.py ../practice-images --query "a photo of a cat" --cache
```

The default is local-files-only model loading. If the model isn't downloaded, the command fails with instructions rather than silently downloading it. `--download-model` permits fetching missing model files; it doesn't upload the input collection. You can additionally set `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` when checking an offline run.

The command considers up to ten readable images in filename order and returns the top five. Change these with `--limit 100 --top-k 5`. It doesn't search PDFs or run OCR. PDF text search stays in the existing command. For now, each command is a separate experiment.

#### What the model does

We use `openai/clip-vit-base-patch32` at revision `c7244be81152024ce0e99ac8d2e373a8953d9f9a`, an explicit safetensors conversion revision in the original model repository. Pinning the revision keeps the downloaded weights and preprocessing configuration stable. We load safetensors weights explicitly rather than relying on automatic format selection. The actual installed dependency versions are also part of the embedding-cache identifier.

CLIP has two matching **encoders**: one takes an image, the other takes text. Each produces an **embedding**, a list of numbers. In this model the list has 512 numbers. These aren't hand-written object tags, and individual positions don't have simple labels like "cat ears". The learned pattern lets us compare related images and descriptions.

For images:

```text
original → correct orientation → RGB → model preprocessing → image encoder → vector
```

For a query:

```text
description → tokenizer → text encoder → query vector
```

The processor takes care of the model's expected image resizing, center crop, pixel normalization, and text tokenization. A **tokenizer** turns text into the numbered tokens the model accepts. Long descriptions are truncated to the model's 77-token input limit. We use the processor distributed with the same pinned model, rather than inventing preprocessing that might produce incompatible results. The center crop can lose content near the edges of an image; that's a retrieval limitation to inspect.

We chose Hugging Face Transformers to load the matching model and processor, and PyTorch to execute the neural-network calculations. Everything currently runs on CPU for a straightforward baseline. GPU/Metal optimization is a later measurement, not a requirement for this small experiment.

`model.eval()` selects evaluation behavior. `torch.inference_mode()` avoids recording information needed for training. Neither updates the model weights. Using existing learned weights is **inference**; changing them using training examples would be **training**.

#### How similarity becomes a ranking

We first normalize each vector to length one. For a small example, `[3, 4]` has length `sqrt(3² + 4²) = 5`, so its normalized form is `[0.6, 0.8]`.

Then we multiply corresponding elements of the query and image vectors and add those products. That is a **dot product**. For unit-length vectors, it is also their **cosine similarity**. We sort the images from highest score to lowest and return at most `--top-k` results. Tied scores use file-path order for repeatability.

The output includes scores and paths, not captions or automatically confirmed labels. A score isn't a probability that an image contains the object. Something ranks first even if the folder contains no cats. There is no calibrated no-match threshold yet. Try a description that matches an image you actually added, then compare unrelated descriptions and inspect the rankings.

The `ClipEncoder` class keeps the model, processor, and library together in one object. `__init__` initializes that object, `self.model` stores its model, and its `encode_image()` and `encode_text()` methods use the same configuration. This is our first application class; you don't need classes to understand the earlier dictionary-based readers.

`**inputs` passes a dictionary's entries as named function arguments. A tensor is PyTorch's numerical array; `.tolist()` converts a result into ordinary Python numbers we can save as JSON. The list comprehension in vector normalization applies the same division to every number. The `lambda` in sorting is a short function that supplies a result's sort key.

With `--cache`, image vectors are saved using the existing SQLite cache. The key includes the model ID, exact revision, preprocessing version, CPU mode, and installed Pillow/PyTorch/Transformers versions. Changed files are re-encoded. Images removed from the folder aren't returned, though old cached rows remain until the database is removed. Query vectors are calculated on each run. Without `--cache`, image vectors aren't saved. The text cache and vector cache use different reader identifiers.

Each command prints model-loading, indexing, and query durations separately. A cached command still starts Python and loads the model; its reported query time doesn't include that startup. For a later local API we could keep the model in memory between requests. Don't mistake a warm vector cache for a continuously running model service.

The vector tests don't require model downloads. They check normalization, cosine scores, ranking, deterministic ties, result limits, and invalid or mismatched vectors. Those arithmetic checks don't prove the model understands your collection; we also need labeled visual queries and inspection of real results.

Initial verification used our eight practice images on macOS with Python 3.13.7, PyTorch 2.14.1, Transformers 4.57.6, and Pillow 12.3.0, running on CPU. The query "a photo of a laptop computer" ranked the laptop product image first. We then disabled network connections during a local model/query run and confirmed all eight image vectors were reused without calling the image encoder. The full suite passed 20 tests. This is a pipeline smoke check, not a labeled accuracy benchmark or proof that cat queries work on a collection without cats.

References: [CLIP model and processor documentation](https://huggingface.co/docs/transformers/v4.56.0/en/model_doc/clip), [pinned model revision](https://huggingface.co/openai/clip-vit-base-patch32/tree/c7244be81152024ce0e99ac8d2e373a8953d9f9a).

### 8. Bring text and visual search into one command

The two experiments worked independently. Next we wanted to ask one query, choose a search approach, and get results in one consistent shape. We added `search_files.py` to coordinate the existing readers rather than copying their implementation.

From `experiments`, with the environment activated, text-only search works with the base dependencies:

```sh
python search_files.py ../practice-images --mode text --query "a phrase from your PDF" --cache
```

For visual search, install `.[visual]` as described in step 7 and download the pinned model once. Then:

```sh
python search_files.py ../practice-images --mode visual --query "a photo of a laptop computer" --cache
```

For the combined mode on macOS, install both optional groups and include OCR if you want screenshot words searched too:

```sh
python -m pip install -e ".[ocr,visual]"
python search_files.py ../practice-images --mode hybrid --ocr --query "your phrase" --cache
```

`hybrid` is the default mode. Add `--download-model` to a visual or hybrid first run if the model hasn't been downloaded. Model loading is otherwise local-files-only. Text mode never loads CLIP. Visual mode never reads PDF text and rejects `--ocr` rather than silently ignoring it. Without `--ocr`, text matching covers extracted PDF text only. OCR dependencies are required whenever you request OCR.

#### Select the same collection for both branches

The new command first selects supported files in filename order, then passes that selection into both readers. `--limit 10` means at most ten candidate files, shared between the text and visual branches. A failed read consumes its candidate slot; we don't silently replace it with a different file in one branch. This differs from the original experiment commands, whose limits count successful reads.

In text and hybrid modes, PDFs and images both count toward this limit. In visual mode, only images are candidates. We still don't enter subfolders. Use a larger limit to include more files. A hybrid selection containing only PDFs skips model loading and searches their text; an actual model-loading error with selected images is reported rather than quietly changing the search mode.

#### How the results are combined

An OCR match and a cosine similarity score measure different things, so we don't add those raw scores together. We use a small **reciprocal rank fusion** baseline. Each branch contributes according to rank rather than the original score:

```text
contribution = 1 / (60 + rank)
```

Our exact phrase matcher doesn't distinguish one matching page as more relevant than another, so every exact match is tied at rank 1. Visual results have their usual similarity ranks. An image that appears in both branches receives both contributions:

```text
Exact phrase match: 1 / 61
Visual rank 2:     1 / 62
Combined score:   about 0.03252
```

The constant 60 smooths the differences between nearby ranks. This is a starting choice, not a value we've tuned on your files. The tied keyword treatment is our adaptation for a boolean phrase matcher; we aren't using BM25 or claiming a complete full-text ranking system. See [Microsoft's explanation of reciprocal rank fusion](https://learn.microsoft.com/en-us/azure/search/hybrid-search-ranking) for the general idea. Our implementation is entirely local and doesn't use Azure.

We combine all selected candidates before returning `--top-k` results. Returning only five visual candidates before fusion could miss an image whose text match should lift it into the final five.

**Deduplication** means keeping one result for the same image even when both branches find it. We use `(path, page)` as the identity: a tuple containing the source path and page number. For an image, `page` is `None`. PDF pages remain separate results because page 1 and page 2 are different locations. Duplicate entries from a single branch don't earn additional score.

After fusion we sort by score, then evidence count, then path and page to make ties repeatable. A result's dictionary contains:

```python
{
    "path": "/photos/example.jpg",
    "page": None,
    "score": 0.03252,
    "score_kind": "rank-fusion",
    "evidence": [
        {"method": "image-ocr", "rank": 1},
        {"method": "clip-visual", "rank": 2, "cosine": 0.24},
    ],
}
```

These numbers are illustrative. `evidence` explains why a result was retrieved; a visual suggestion isn't a confirmed object label, and an OCR match can still come from a recognition error. The terminal prints the method names without printing extracted contents.

Text mode labels its score `exact-match`; visual mode labels it `cosine`; hybrid labels it `rank-fusion`. These score types aren't interchangeable and none are calibrated probabilities. Visual-only candidates can still appear when there is no exact match, including for queries unrelated to the collection. There is no no-match threshold yet. Use text mode when you want only literal phrase matches.

The `search_files()` function returns a list of result dictionaries. The terminal entry point displays them. This gives us a shared retrieval interface for later experiments and a local API, but the current readers also print progress; we haven't built a server or finalized an API contract yet.

Tests check merging both sources, tied text ranks, duplicate suppression, separate PDF pages, limits, mode isolation, and a shared candidate pool. Model loading is mocked in orchestration tests so they run without downloads. These tests establish consistent behavior; labeled queries are still needed to learn whether fusion improves relevance.

Initial verification passed all 31 tests. On the practice folder, the offline hybrid laptop query reused nine text records and eight image embeddings and ranked the laptop image first. A second real-data check used a recognized word from an image and verified that the image appeared once with both OCR and visual methods attached. Text-only retrieval was also checked without loading CLIP. These are behavior checks, not a relevance benchmark.

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

- `Python tuple dictionary keys`: how `(path, page)` identifies a result.
- `Python sets membership`: how we avoid counting the same visual result twice.
- `Python dictionary values`: how merged records become a result list.
- `Python sorted tuple key`: how multiple sorting criteria break ties.
- `reciprocal rank fusion`: why we combine ranks rather than raw scores.

The visual-search step introduced:

- `machine learning inference vs training`: why we can use a model without training one.
- `image text embeddings CLIP`: why images and descriptions can be compared.
- `vectors normalization cosine similarity dot product`: how we compute rankings.
- `Python classes init self methods`: how we keep the encoder and processor together.
- `Python list comprehensions`: applying an operation to every vector element.
- `Python dictionary unpacking kwargs`: what `**inputs` does.
- `Python sorted key lambda`: how we order scores and break ties.

The caching step introduced:

- `Python sqlite3 tutorial`: opening a local database, executing SQL, and committing writes.
- `Python json dumps loads`: saving dictionaries as text and restoring them.
- `Python pathlib stat st_mtime_ns st_size`: checking whether a source file changed.
- `Python contextlib contextmanager yield finally`: opening and closing resources reliably.

The OCR step introduced:

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

We now have one command with text, visual, and hybrid modes. Next we'll label expected results for a small set of queries and compare the modes before tuning ranking or connecting a local interface. OCR for scanned PDFs is another separate step. Each feature gets its own verification and Git commit, separate from frontend changes.

The broader path is Python engine → useful retrieval → local interface/API → gradual Rust migration. A small FastAPI service could later keep the Python model loaded and expose stable result shapes to a local frontend. There is no API server yet, and the public website doesn't have access to your folders. We can replace individual engine responsibilities with Rust after comparing their outputs against the Python reference. The intended shipped desktop app should work without a Python interpreter.

Later, we'll compare keyword and semantic retrieval on labeled queries, and test whether relationships such as receipts belonging to trips improve results. Models may propose relationships; evidence and user confirmation need to stay distinguishable. We will measure useful behavior before moving it into the Rust engine. Python is our development reference, not a required runtime for the intended desktop release.

See the [project overview](../README.md), [architecture](../docs/architecture.md), and [implementation plan](../plan.md).
