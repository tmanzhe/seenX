# Portable Python libraries

The first slice of roadmap item 06 supports whole-library export, restore, and verification through the trusted local `seenx-memory` CLI. It covers the Python catalog; native capture storage and selected-collection exports remain separate work.

From the repository root, with the existing environment installed:

```sh
# Export all referenced revisions and their context, or context without image bytes.
uv run --no-sync --project python seenx-memory --library /path/to/library export /path/to/complete.zip --mode complete
uv run --no-sync --project python seenx-memory --library /path/to/library export /path/to/context.zip --mode context-only

# Verify archives without writing files.
uv run --no-sync --project python seenx-memory verify /path/to/complete.zip
uv run --no-sync --project python seenx-memory verify /path/to/context.zip --original-folder /path/to/originals

# Both destinations must be absent, including an empty directory or symlink.
uv run --no-sync --project python seenx-memory --library /path/to/new-library restore /path/to/complete.zip
uv run --no-sync --project python seenx-memory --library /path/to/new-context-library restore /path/to/context.zip --original-folder /path/to/originals

# Verify managed snapshots, optionally reporting possible relinks.
uv run --no-sync --project python seenx-memory --library /path/to/new-library verify
uv run --no-sync --project python seenx-memory --library /path/to/new-context-library verify --original-folder /path/to/originals
```

`import FILE` retains its existing image-import meaning; `restore ARCHIVE` imports a library archive. Global options such as `--library` go before the subcommand. Commands print JSON to stdout and diagnostic run IDs to stderr. `verify` returns exit status 1 for missing files or checksum mismatches (and for invalid archives); successful verification returns 0.

The ZIP contains `manifest.json`, `catalog.json`, and, in complete mode, `objects/SHA256`. Manifest format version 1 records `archive_format_version`, `catalog_schema_version` (currently 4), `mode`, UTC `created_at`, and a `files` mapping from every payload path to its SHA-256 checksum. The manifest excludes its own checksum. These are corruption checks, not authentication or encryption. Both metadata and images are unencrypted.

The catalog payload preserves stable IDs, revision/source history, notes, selected text, OCR runs/observations and provenance, quote links, normalized highlight/point targets, collections, and membership. Absolute source paths remain historical metadata; restore never reads them to find originals. Only referenced objects are included, so logically removed images, unrelated files, caches, thumbnails, and derived search indexes do not travel. Export reads one SQLite transaction and checks every written payload and catalog relationship before publishing a new archive. Existing archive destinations are refused.

Restore constructs a fresh database using the application's schema and constraints, rebuilds FTS5, validates references/duplicate IDs, and stages image bytes before publishing into a newly created target. Archive format versions other than 1 and catalog schema versions other than 4 are rejected. Existing version 1–3 libraries must first be opened with `Catalog` (for example, `seenx-memory --library PATH list`) to run the normal catalog migration before export. No archive migration or merging is implemented in this slice. Unsafe paths, duplicate members, symlinks, unlisted payloads, missing complete-mode files, and corrupt payloads are rejected before creating the destination library.

Context-only restore can succeed without originals: notes/OCR remain searchable, while image fetch fails until snapshots are available. Its JSON reports `restored: true`, `ok: false`, and the missing object paths. An optional `--original-folder` is scanned recursively by content hash, allowing renamed files and historical revisions to match. Symlinks are skipped. Matching bytes are copied into managed objects during restore; external files remain untouched. No machine's original absolute paths are trusted for resolution.

Verification returns `missing_files`, `checksum_mismatches`, and `relinked_files`. A relink entry contains the managed object path and matching `original_path`; an unresolved context revision is reported missing. Library verification reports potential matches without copying them. To materialize those matches, restore the archive again to another new path with `--original-folder`. Corrupt managed objects remain checksum errors rather than being silently replaced.

**Grants deliberately do not transfer.** Per roadmap item 06, both source and collection grant tables are excluded; restore also rejects unexpected catalog tables. Collections/membership survive, but every restored library starts deny-by-default for assistants. Reauthorize source/collection access on the destination with the existing owner `grant` commands. Credentials, tokens, and machine-specific permissions are not included.

The `dev` dependency group now includes pytest; the lockfile is intentionally unchanged in this slice. Existing unittest-style tests are also pytest-compatible. Without changing the environment or lockfile, run the installed interpreter directly:

```sh
PYTHONPATH=python/src python/.venv/bin/python -m unittest discover -s python/tests -v
```
