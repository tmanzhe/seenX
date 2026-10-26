# seenX in Python

This is the working Python retrieval prototype. The website lives separately in `apps/web`, and the native Swift app lives in `apps/macos`. We use Python to learn the pipeline and measure behavior before integrating proven pieces into the native app.

The [detailed walkthrough](docs/walkthrough.md) follows how we built each piece and explains the Python concepts along the way.

The first durable memory slice is also implemented: import a real image, attach a whole-image/point/region note, and recover its exact revision after restart. See [the catalog lesson](docs/catalog.md) for the commands and rationale. Its database is separate from the extraction cache.

The catalog now also saves OCR text regions and lets notes quote their stable observation IDs. Existing catalogs migrate additively to version 2. Follow [the OCR observation lesson](docs/ocr-observations.md) for coordinate conversion, provenance, and the migration tests.

## Start here: uv manages the environment

From the repository root:

```sh
uv sync --project python --all-extras
uv run --project python seenx-search practice-images --mode hybrid --ocr --cache --query "basketball"
```

`uv` is already installed on the development Mac. On a new Mac, install it with `brew install uv`, or follow the [official installation instructions](https://docs.astral.sh/uv/getting-started/installation/).

You don't need to create or activate an environment manually. `uv sync` reads `pyproject.toml` and `uv.lock`, creates `python/.venv`, and installs the selected dependencies. `.python-version` pins our development interpreter to Python 3.13.7. `uv run` executes a command in that environment. Keep this as the project's only Python environment; use `--project python` from the repository root instead of creating a second root `.venv`.

The first sync downloads Python packages. Visual search also needs the pinned model, a separate download of roughly 600 MB. If it isn't already present, allow the first model download explicitly:

```sh
uv run --project python seenx-visual practice-images --query "a photo of a laptop" --cache --download-model
```

Later model loads use local files unless downloads are requested. Your photos and documents aren't uploaded. `practice-images/` is the repository-root input folder, ignored by Git; another existing folder path works too.

`--all-extras` installs the optional `ocr` and `visual` groups. OCR currently requires macOS. For PDF text-only work, plain `uv sync --project python` installs the base project. A later plain sync removes unselected extras, so use `--all-extras` for the full toolkit. `uv run` normally preserves already-installed extras. See [uv's sync behavior](https://docs.astral.sh/uv/concepts/projects/sync/).

The committed lockfile records exact dependency versions. Use `uv sync --project python --all-extras --locked` to require it to stay unchanged. We commit that file, not the generated virtual environment.

## Commands you'll use

All examples start at the repository root:

```sh
# Inspect metadata without OCR or a visual model.
uv run --project python seenx-inspect practice-images

# Literal PDF text search; add --ocr to include screenshot words.
uv run --project python seenx-search practice-images --mode text --query "your phrase" --cache

# Search what images look like.
uv run --project python seenx-search practice-images --mode visual --query "a laptop" --cache

# Combine exact text matches and visual suggestions.
uv run --project python seenx-search practice-images --mode hybrid --ocr --query "basketball" --cache

# Save more detailed diagnostic events.
uv run --project python seenx-search practice-images --query "your phrase" --ocr --cache --debug

# Save a real image revision (replace the filename), then list the library.
uv run --project python seenx-memory import "practice-images/my-screenshot.png"
uv run --project python seenx-memory list

# Recognize a saved revision, then quote one of its observation IDs.
uv run --project python seenx-memory ocr REVISION_ID
uv run --project python seenx-memory note REVISION_ID --note "Keep this detail" --observation OBSERVATION_ID

# Run the automated tests.
uv run --project python python -m unittest discover -s python/tests -v
```

Use `--help` on any command. If you prefer working inside this folder, run `cd python` and omit `--project python`; the input folder then becomes `../practice-images`.

The commands are entry points declared in `pyproject.toml`. `seenx-search`, for example, calls `seenx.search_files.main`. You can also use `uv run --project python python -m seenx.search_files practice-images --query "a laptop" --cache`. You don't need to execute files inside `src` directly.

The default search mode is `hybrid`. `--limit` defaults to ten candidate files and `--top-k` is a maximum of five accepted results. Increase the candidate limit for larger collections. We don't enter subfolders yet. The original learning commands remain available as `seenx-inspect` and `seenx-visual`. `seenx-memory` manages durable records; those notes aren't connected to search yet.

## Understand the two search branches

| Branch | What it searches | What a match means |
| --- | --- | --- |
| Text | Extracted PDF text and, with `--ocr`, recognized image words | The normalized literal phrase occurs in that text |
| Visual | CLIP embeddings of image pixels | The model gives the image a sufficiently similar representation to the description |

Text search doesn't search filenames or understand synonyms. The visual branch doesn't process PDF pages. A PDF whose filename includes `bloodwork` can therefore return nothing when its extracted text doesn't contain that word. Searching `test` can return separate pages containing `test`, plus a visually suggested image. The image need not contain the written word.

Hybrid mode merges those branches using rank fusion, keeping the retrieval methods attached and deduplicating images found by both. A single rank-one contribution is `1 / 61`, about `0.016393`. Two different result types can have the same number. It is a ranking contribution, not confidence that either result is correct.

## How we're checking accuracy

We fixed a clear behavior bug: returning the top five nearest pictures filled the list even when only one was relevant. Visual candidates now need to pass `--min-score` before fusion. Its default is `0.25`; raising it is stricter, lowering it permits more suggestions. It is a cosine cutoff, not 25% confidence.

On the practice collection, basketball and laptop each return one result, while an unrelated submarine query returns zero. These are useful regression checks. They don't prove the cutoff works for every object or collection.

Automated tests check implementation rules: filtering, sorting, cache invalidation, duplicate suppression, and error handling. Measuring relevance requires queries with expected matches labeled before running them. We need positive and no-match examples, then compare text, visual, and hybrid modes for unwanted results and missed relevant files. Logging explains errors; it doesn't train or improve the model by itself.

## What caching means

A cache is saved work. Instead of extracting the same PDF text or re-encoding an unchanged image on every query, we reuse the previous result.

With `--cache`, PDF/OCR text and image vectors are saved in `.cache/records.sqlite3` inside this folder. SQLite is a database in a local file; it needs no server. We store records as JSON, a text representation of Python dictionaries and lists.

Each scan checks the source path, file size, modification timestamp, and reader/model settings. If they match a saved row, it's a **cache hit**. Otherwise it's a **cache miss** and extraction runs again. Different extraction modes and versions use different keys. The timestamp/size check is a shortcut, not a content hash: deliberately preserving both can hide a change.

Saved rows survive closing Python or restarting the Mac. There is no expiry timer today. Removed files stop appearing on the next scan, but old rows stay on disk until the database is cleared. To clear extraction data, stop the program and delete `python/.cache/records.sqlite3`. That doesn't delete the originals or model download. The database is unencrypted local data and ignored by Git.

Your own notes belong in the separate `python/library/catalog.sqlite3`, with managed image snapshots under `python/library/objects/`. Clearing `.cache` leaves them intact. The library is durable personal data and is also ignored by Git. It isn't a backup by itself; portable backup/restore remains planned.

Caching is not learning. It doesn't change model weights, recognize new concepts, or remember whether you liked a result. Query vectors are computed again. Each new terminal process still loads the model into memory, even with cached image vectors; a future service could keep the model instance alive between requests.

Model files live separately in repository-root `models/huggingface/`. Package downloads in uv's own cache are a third, unrelated cache.

## Logging and observability

**Logs** record events. **Metrics** measure counts and durations. **Observability** means using that information to understand why a run behaved as it did.

Both search commands write local JSONL events to `.cache/logs/search.jsonl`. JSONL means one JSON object per line. Each command prints a run ID shared by its events. This code doesn't export logs to a monitoring service.

Events show exact text match counts, accepted/rejected visual candidates, cache statistics, and time spent loading the model, extracting, encoding, ranking, and fusing. Failures record their stage and error type. Some stages contain others, so their durations overlap; don't sum them as though they were a total.

Add `--debug` for individual cache and score decisions. Miss reasons distinguish a new file, another reader variant, a changed source, and malformed cached JSON. Saved events omit raw query text, full source paths, extracted contents, vectors, and exception messages. File IDs correlate work within one run. Terminal results still show matching paths.

From the repository root:

```sh
tail -n 20 python/.cache/logs/search.jsonl
```

The file rotates at about 1 MiB with three backups, roughly 4 MiB total. This is size-based retention for our local CLI; a multi-process server needs another collection setup. `--no-log` disables persistent diagnostics, not extraction caching. Deleting logs doesn't clear the database or model files. See the [logging walkthrough](docs/walkthrough.md#10-understand-a-run-with-logging) for the event map and implementation.

## Folder map

```text
python/
  README.md                 Setup and the concepts to understand first
  pyproject.toml            Dependencies and command entry points
  uv.lock                   Exact dependency resolution; committed
  .python-version           Development interpreter version
  src/seenx/
    load_images.py          File reading and literal text matching
    image_ocr.py            macOS Vision OCR adapter
    visual_search.py        CLIP model, embeddings, and visual ranking
    search_files.py         Shared text/visual/hybrid retrieval
    record_cache.py         SQLite storage and freshness checks
    observability.py        JSON events, counters, and timers
    paths.py                Repository/cache/model locations
    catalog.py              Durable assets, image revisions, regions, and notes
    catalog_migrations.py   Transactional schema upgrades
    catalog_ocr.py          Immutable OCR runs, observations, and provenance
    memory_cli.py           Import/annotate/fetch/edit/remove commands
  tests/                    Automated behavior checks
  docs/walkthrough.md       How we built each piece and why
  docs/catalog.md           The first durable-memory lesson
  docs/ocr-observations.md   Recognized boxes and quoted-note provenance
  .venv/                    Generated by uv; ignored
  .cache/                   Personal extraction cache and local logs; ignored
  library/                  Durable catalog and image objects; ignored
```

`src/seenx` is a Python package: a named collection of modules that import each other as `from seenx...`. Tests are separate from application code. `paths.py` keeps local data locations independent of the terminal's current directory. The move preserved the extraction cache and model downloads; personal inputs stayed in `practice-images/`.

## Learning order and next step

Start with variables, functions and return values, lists, dictionaries, conditions, and loops. Then learn exceptions and `with` statements. For recent work, look up `Python logging handlers formatters`, `Python contextvars`, `Python decorators`, `JSON Lines`, `SQLite`, and `uv projects lockfile`.

The [walkthrough](docs/walkthrough.md) explains the retrieval code step by step. The [catalog lesson](docs/catalog.md) explains stable IDs, foreign keys, transactions, hashes, and normalized coordinates. The [OCR lesson](docs/ocr-observations.md) adds immutable observations, quote links, and schema migrations. Next, connect catalog notes and observations to retrieval using FTS5, while measuring relevance with labeled examples. No Python API server exists yet; the public website runs separately. Native integration follows proven behavior behind shared contracts.
