# Save one image and a thought that survives a restart

This is the first slice of the visual-memory product. The existing search commands read a folder and retrieve candidates. The new `seenx-memory` command saves image revisions and your own annotations in a durable local catalog. It uses SQLite and Pillow, which we already have; there is no new framework or model.

The goal for this step is deliberately small: import an image, attach a region note, close the process, then recover the same image version and aligned note.

## 1. Import an existing image

From the repository root, replace the filename below with an image you added:

```sh
uv sync --project python --all-extras --locked
uv run --project python seenx-memory import "practice-images/my-screenshot.png"
```

The command prints JSON with `asset_id`, `revision_id`, a SHA-256 hash, and orientation-corrected dimensions. Keep the two IDs for the following commands. Diagnostic run IDs go to stderr, leaving stdout as JSON.

The original stays untouched. The library preserves an exact byte-for-byte snapshot under `python/library/objects/`. This copies the real input; it doesn't generate a new picture or a thumbnail. The snapshot retains original orientation metadata. Consumers must apply EXIF orientation before displaying annotation coordinates.

## 2. Attach a note to the exact version

Replace `REVISION_ID` with the value returned by import:

```sh
uv run --project python seenx-memory note REVISION_ID \
  --note "Keep this spacing, but try a softer color" \
  --selected-text "Continue to checkout" \
  --region 0.25 0.50 0.20 0.10
```

Those four coordinates mean `x`, `y`, `width`, and `height`, measured from the top-left of the full orientation-corrected image. They are normalized fractions, not screen pixels:

- `x = 0.25`: start a quarter of the way across.
- `y = 0.50`: start halfway down.
- `width = 0.20`: cover 20% of the image's width.
- `height = 0.10`: cover 10% of its height.

The region must fit inside `[0, 1]` and have positive width and height. For a point use `--point 0.4 0.6` instead. Omitting both makes a whole-image note. A note or selected text is required; selected text alone is allowed. Text supplied here is a user selection, not an OCR-verified quote. Native selection and OCR box grounding come later.

The result includes `annotation_id` and `region_id`. The annotation records its origin as `user` and confirmation as `confirmed`: it was explicitly supplied through this command, not inferred by a model. We don't support model-proposed catalog annotations yet.

## 3. Recover it in another process

Replace `ASSET_ID` with the import result:

```sh
uv run --project python seenx-memory list
uv run --project python seenx-memory get ASSET_ID
```

Every command starts a new process. `get` retrieves the saved note, selected text, normalized target, and corresponding pixel bounds. It also checks the snapshot's hash and returns its local path. For rectangular bounds, right/bottom are exclusive edges; points use pixel indices, with coordinate 1 mapping to the last pixel. Floating-point rounding near integer boundaries is handled so a region doesn't accidentally expand by one pixel.

The response includes typed links: annotation `refers_to` region, region `part_of` image revision, revision `revision_of` asset. These are derived from foreign-key relationships in the database. We haven't introduced a separate graph database or a general relationship-inference system.

## Why there are several IDs

| Concept | What it identifies | Why it exists |
| --- | --- | --- |
| Asset | A library item imported from a particular source path | Stable identity across later versions of that source |
| Revision | One exact version of its bytes | Keeps old notes attached to the image you actually annotated |
| Region | A whole-image, point, or rectangle target on a revision | Makes "this part" explicit |
| Annotation | Your note and optional selected text | Editable personal context with its own identity |

An ID is a generated UUID label. A SHA-256 hash is a fingerprint of exact file bytes. A CLIP embedding describes learned features for approximate visual comparison. These three things serve different purposes.

Re-importing the same source path and unchanged bytes reuses the asset and revision IDs. Re-importing changed bytes at that path creates a new revision under the same asset. The current revision changes, while old notes remain attached to the old one. Returning the source to earlier bytes reuses that earlier revision.

`get` includes revision history and annotation counts so older IDs can be discovered. Fetch an older version explicitly:

```sh
uv run --project python seenx-memory get ASSET_ID --revision OLD_REVISION_ID
```

A renamed source path currently creates a separate asset on import; relinking isn't implemented. Identical image bytes imported from two paths can share a snapshot file, while keeping separate asset identities. The catalog doesn't infer that different source paths should be one logical memory.

## Edit and remove

```sh
uv run --project python seenx-memory edit ANNOTATION_ID --note "Updated thought"
uv run --project python seenx-memory delete-note ANNOTATION_ID
uv run --project python seenx-memory remove ASSET_ID
```

Editing preserves the annotation ID and target. Changing a target is a later operation; currently create another annotation and delete the old one. Deleting an annotation removes its target without deleting the image. Removing an asset removes its catalog revisions and annotations. Repeating a removal returns `removed: false` instead of failing.

Removal leaves imported originals untouched. Content-addressed snapshot objects are currently retained, including unreferenced ones; another asset may use the same bytes. Garbage collection and secure erasure aren't implemented. This is logical removal from the catalog, not a promise to erase all disk copies.

## Durable catalog versus cache

The default catalog is `python/library/catalog.sqlite3`, with image objects next to it. The extraction cache remains `python/.cache/records.sqlite3`. Both directories are ignored by Git. **Clearing the extraction cache doesn't delete notes. Deleting the library does.**

For an isolated library, put the global option before the subcommand:

```sh
uv run --project python seenx-memory --library /path/to/my-library list
```

If an original goes missing, saved evidence still comes from its managed snapshot. A missing or modified snapshot produces an explicit error and doesn't discard the database notes. Re-importing intact original bytes can restore a missing snapshot. An existing corrupt snapshot is reported rather than silently overwritten.

Snapshots are published only after all bytes are written, then database records commit. An interrupted import may leave an unreferenced object; we prefer that to a committed record pointing at a partially written image. Filesystem writes and SQLite writes aren't one shared transaction. Full backup/restore, crash recovery, and storage reclamation remain later milestones.

## The Python and database concepts in this step

- **Primary key:** the unique ID for one row, such as an annotation ID.
- **Foreign key:** an enforced reference to another row. An annotation can't point at a nonexistent region.
- **Transaction:** a group of database changes that commit together or roll back together. Region and note creation use one transaction, so a failure can't save half the annotation.
- **Schema version:** the database layout's version. We initialize version 1 and reject unknown versions. Future migration steps will be added as the schema changes; we don't silently downgrade a newer catalog.
- **Content-addressed storage:** name a stored object using its byte hash. Identical bytes can reuse the same object. Hash checks detect later snapshot damage.
- **Class/context manager:** `Catalog` keeps a database connection together with its operations; `with Catalog(...)` closes the connection reliably.
- **Provenance:** retain where information came from. Imported evidence and user-written meaning have different origins.

The catalog commands share our local diagnostics. Logs include operation names and stable record IDs, not note contents, selected text, image bytes, or full source paths. The JSON returned by `get` intentionally includes the requested note and source reference. `--no-log` disables persistent diagnostics; it doesn't disable saving memories.

## What this completes—and what comes next

This step proves import → annotate → restart → recover, with changed/missing-original handling, snapshot verification, and transactional edit/delete behavior. The tests use placeholder bytes and mocked image decoding, not generated image fixtures. We also exercised the CLI in separate processes using existing practice photos in an isolated temporary library; the original practice files were unchanged.

The current search command still searches selected folders and derived caches. It doesn't yet search catalog notes. There is no native annotation UI, OCR-box selection, FTS5 catalog index, thumbnail generator, complete-library archive, encryption, source/collection authorization, local service, or MCP endpoint in this slice.

Next: extend Vision OCR to retain boxes in the shared coordinate system, then connect selected text and notes to catalog retrieval. Collections, tags, richer assertions, migrations beyond version 1, and export/restore remain part of the larger roadmap.
