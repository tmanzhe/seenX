# Keep recognized words attached to their image locations

The previous step saved image revisions and region notes. This step gives OCR the same spatial grounding: each recognized text region has a stable observation ID, a box on an exact image revision, and explicit model provenance.

We still use Pillow, macOS Vision, and SQLite. No OCR service, new model download, or additional dependency is introduced.

## The flow you can try

From the repository root, install the existing OCR extra and import an image containing text:

```sh
uv sync --project python --extra ocr --locked
uv run --project python seenx-memory import "practice-images/my-screenshot.png"
```

Replace the path with an image you added. Copy its returned revision ID, then run:

```sh
uv run --project python seenx-memory ocr REVISION_ID
```

The command reads the library's hash-verified snapshot, not the current contents of the original file. Output includes an OCR run ID, its recognition configuration, and observations. Each observation contains recognized `text`, native `confidence`, a normalized `box`, its position in the returned sequence, and these provenance fields:

```json
{
  "origin": "ocr",
  "confirmation": "unverified"
}
```

These are currently text-region/line boxes. Character ranges, individual word selection, and native text selection aren't implemented. The model's observation order is preserved; we don't claim it reconstructs all document reading orders perfectly.

To attach a thought to one saved observation, copy its ID:

```sh
uv run --project python seenx-memory note REVISION_ID \
  --note "Use this spacing" --observation OBSERVATION_ID
uv run --project python seenx-memory get ASSET_ID
```

`--observation` supplies the recognized text and its region, so it can't be combined with `--region`, `--point`, or a custom `--selected-text`. The observation must belong to the same image revision. Both the application and SQLite enforce that boundary. A note can contain an observation quote even if its own note body is empty.

`get` now returns OCR runs for the selected revision and the annotation's `quoted_observation_id`. The relationship list includes annotation `quotes` observation. Selecting a box is an explicit user action; it doesn't prove the transcription is correct. The annotation's selected-text fields retain `selected_text_origin: "ocr"` and `selected_text_confirmation: "unverified"`.

## Why the vertical coordinate changes

[Vision defines normalized boxes with a bottom-left origin](https://developer.apple.com/documentation/vision/vndetectedobjectobservation/boundingbox). Our catalog and future interface use the top-left of the full orientation-corrected image.

For a Vision box `(x, y, width, height)`, we convert:

```text
catalog_x = x
catalog_y = 1 - y - height
catalog_width = width
catalog_height = height
```

For example, Vision `(0.1, 0.7, 0.3, 0.1)` becomes top-left `(0.1, 0.2, 0.3, 0.1)`. The subtraction includes the height because we're locating the top of the rectangle rather than its bottom.

Pillow applies EXIF orientation before OCR. Dimensions returned by recognition must match the catalog revision's orientation-corrected dimensions before saving. Nonfinite, empty, and out-of-bounds boxes are rejected. The adapter tolerates only tiny floating-point errors at the image boundary. Display scaling, letterboxing, and screen-to-image conversion still belong to the future interface.

[Apple also notes that recognized-text boxes aren't always an exact fit](https://developer.apple.com/documentation/vision/vnrecognizedtext/boundingbox%28for%3A%29). These boxes guide annotation; they don't establish pixel-perfect text segmentation.

## Recognition is reproducible evidence, not editable truth

An OCR run's identity combines the image revision with a hash of its configuration. The recorded configuration includes the engine, Vision request revision, adapter version, operating-system version, PyObjC version, language, recognition level, language correction, and coordinate convention.

Running the command again with the same revision/configuration reuses the saved run and observation IDs, including a successful run with no recognized text. Failed recognition doesn't create a successful empty run. The snapshot hash is still verified when requesting recognition, even if observations already exist.

A changed configuration creates another immutable run rather than overwriting the observations that existing notes quote. Old observations and links remain available. We don't offer a destructive refresh of linked OCR evidence.

Editing only the note body preserves its quote. Supplying `--selected-text` explicitly makes that text user-authored: it detaches the previous quote and marks the selected text's origin as `user`. The original OCR observation is retained unchanged. This preserves the distinction between the model's initial output and your correction.

There are three different scores in this project:

| Score | What it describes |
| --- | --- |
| Vision confidence | The OCR engine's text-recognition candidate |
| CLIP cosine similarity | Similarity between a visual representation and a description |
| Rank-fusion score | Contributions from result ranks in different retrieval branches |

They aren't interchangeable. Native OCR confidence is recorded as evidence, not presented as a calibrated product-wide probability. It doesn't automatically confirm a recognized fact.

## Catalog version 2 and migration safety

Opening a valid version-1 catalog runs an additive migration under a SQLite write lock. The migration adds OCR runs, text observations, quote links, and selected-text provenance fields. Existing asset, revision, region, annotation IDs, contents, and timestamps are preserved. Existing manual selections keep their user provenance.

The migration commits all changes together and updates the schema version last. An error rolls back the entire migration so opening can be retried. The version is rechecked under the write lock; a second process doesn't blindly repeat the migration. Unknown schema versions and unrelated databases are still rejected.

OCR run creation and all observations are one transaction. Annotation creation, its target, and its quote link are another transaction. Write-failure tests check that neither operation leaves half-saved records. Quoted observations can't simply be deleted while live notes refer to them; removing an entire memory cascades its dependent records together. Managed snapshot-object retention is unchanged from the catalog lesson.

The current application remains a local CLI prototype with a single intended catalog owner. This migration work doesn't add an HTTP service, source/collection grants, MCP access, or backup/restore.

## Compatibility and verification

The existing folder-search interface still receives a combined OCR string through `extract_image_text()`. It joins the structured observations in order. Catalog observations are saved separately; they're not silently inserted into the folder extraction cache or search index.

Tests cover origin conversion, legacy string behavior, observation validation, successful empty runs versus errors, stable observation reuse, configuration changes, quoted-note provenance, cross-revision constraints, correction behavior, snapshot integrity, cascading removal, write failures, and version-1 migration/rollback. They don't require macOS or generated images. A separate real Vision check recognized 21 regions from an existing practice screenshot and verified quoting/restart/reuse in an isolated temporary library without printing the recognized contents.

Logs record operation IDs and counts, never recognized text or note bodies. The `seenx-memory` JSON response intentionally includes requested text and boxes. Your inputs remain untouched.

The next retrieval step is FTS5 over catalog notes, selected text, and observations, with results pointing back to stable evidence IDs. Semantic note embeddings, word/range selection, and a native annotation interface remain later work.
