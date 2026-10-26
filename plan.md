# seenX — product and implementation roadmap

## Product contract

A local visual memory for the things you save and the thoughts you attach to them. One memory engine serves a person through a lightweight search interface and an authorized assistant through MCP.

**V1 loop:** capture → recognize text → highlight/pin → optional note → save → search → retrieve the same evidence through a compatible assistant.

This plan supersedes the earlier sequence that put a broad ontology experiment before annotations and deferred assistant access indefinitely. A bounded, explicit ontology belongs in the memory model; automatic relationship extraction is evaluated later. MCP is in V1 and can be developed in parallel with the native interface once engine contracts exist.

## Current implementation

- **Website:** working authored sample capture, image results, text selection, pins/regions, notes, browser persistence, Command/Ctrl K, and JSON context export. No real image access, OCR, vector inference, or assistant connection.
- **Python:** image/PDF reading, macOS Vision OCR strings/boxes, folder text/visual/hybrid search, caching, diagnostics, and a durable memory catalog. `seenx-memory` supports import, notes/regions, OCR quotes, revision-aware fetch, FTS5 retrieval over saved notes/selections/OCR, transactional edit/remove, and index rebuild. Version-1/2 catalogs migrate atomically to version 3 while preserving source IDs.
- **Native app:** SwiftUI/AppKit menu-bar frontend with translucent search, global shortcuts, system region screenshots, Vision text-box highlights, notes, and its own capture library. An optional **Open Python Library…** browser uses the Python search/fetch engine; the main launcher and capture storage remain separate. See [native setup and shortcuts](apps/macos/README.md).
- **Shared interface:** version-1 local read-only search, memory fetch, and saved-region fetch through `seenx-engine` JSON process pipes, consumed by the typed Swift client. It returns stable evidence IDs, explicit errors, trace IDs, and optional image/crop attachments. Unified capture writes, write/export operations, access grants, and MCP remain unfinished.
- **Word/range selection, semantic note embeddings, sqlite-vec, and catalog visual/text fusion:** not implemented. Lexical catalog retrieval is available through the CLI and optional native catalog browser.

## 01 — Durable local memory + lightweight ontology · IN PROGRESS

Build a versioned SQLite catalog that is separate from the disposable extraction cache.

The image/revision/region/annotation schema and local CLI are implemented. Separate-process checks recover notes and targets after restart and preserve old annotations when sources change or disappear. Version 2 adds immutable OCR runs, normalized boxes, and annotation quote links while preserving existing data. The typed links use foreign keys and revision guards. Collections/tags, richer assertions, word/range grounding, thumbnails, and portable export remain unfinished. See [the catalog lesson](python/docs/catalog.md) and [OCR observations](python/docs/ocr-observations.md).

- Stable asset and immutable revision IDs; content hash, normalized orientation, dimensions, source references, and thumbnails.
- Whole-image notes, selected text, point targets, and rectangular regions using normalized top-left coordinates.
- Text observations with provenance; user notes remain separate from OCR and model descriptions.
- A small typed relationship model: annotation refers to region; region belongs to image revision; image belongs to collection; capture came from source. Include tags and optional user-defined subjects without requiring automatic inference.
- Store assertion provenance and confirmation state. Imported evidence, user labels, and proposed model associations are different facts.
- Schema migrations, save/edit/remove, export, and deliberate handling of missing or changed originals. Preserve imported originals; keep capture snapshots/annotated revisions stable.

**Done when:** import one real screenshot, save a region note, restart, and recover the original image revision, selected text, note, and aligned location. Update/delete operations are transactional and repeatable.

## 02 — Real OCR and hybrid retrieval · V1

The OCR-region persistence and quote-selection slice is implemented and was exercised with real Vision output. It preserves line/region boxes and marks transcription as unverified. Word/range selection remains planned; catalog retrieval is described below.

Catalog FTS5 search is now implemented for notes, selected text, and OCR evidence. Database triggers maintain the derived index transactionally across supported writes/deletion; a version-3 migration backfills existing records. Results return stable source IDs, revision/target data, excerpts, and provenance. Phrase/all-term modes, revision filters, bounded requests, and index rebuild are covered by tests. This is lexical retrieval, not semantic note search or a measured accuracy claim. See [the search lesson](python/docs/catalog-search.md).

- Extend Vision OCR to retain text observations and word/range locations, not just a combined string.
- Normalize Vision coordinates, EXIF orientation, screen points, and image pixels into the shared image coordinate system.
- Add SQLite FTS5 for OCR, highlighted text, and user notes; preserve exact identifier/phrase retrieval.
- Keep compatible image/text encoders for visual similarity. Evaluate a separate text encoder for paraphrases of notes; never compare unrelated embedding spaces directly.
- Prototype sqlite-vec and compare it with exact vector scanning. Final library/runtime selection follows retrieval, packaging, and resource measurements.
- Fuse ranked exact/visual/note results, then preserve source evidence and explicit access/filter constraints.
- Incrementally update indexes after note edits or source changes. Pin model revisions and invalidate stale embeddings deliberately.

**Done when:** a labeled dataset of roughly 50–200 images covers OCR phrases, visual descriptions, note paraphrases, region intent, and genuine no-match queries. Record top-k quality, false matches, indexing time, warm latency, memory, storage, hardware, and model revisions. Reproduce offline after model installation. No accuracy target is claimed before measurement.

## 03 — Shared local engine contract · V1

The read-only slice is implemented: a persistent local process accepts bounded JSON-line requests for capability discovery, catalog search, memory fetch, and saved-region fetch. It checks revision ownership, preserves provenance/coordinate context, omits internal paths, and bounds image attachments. Tests cover invalid input, recovery, limits, and log-content omission; a separate process check decoded a real existing image and crop. See [the engine lesson](python/docs/engine-contract.md). This doesn't finish this milestone: write/export operations, grants, cancellation, and native/MCP integration remain below.

The first native client/browser now uses those operations against an explicitly selected Python library. Helper-process tests cover framing, decoding, limits, method errors, concurrent callers, timeout/cancellation, and shutdown. Native model tests protect against stale results and fatal-transport state; an opt-in real-engine test verifies actual search, image/crop decoding, OCR/point targets, and unchanged original bytes. See [the integration lesson](docs/native-engine.md). Main-launcher capture integration and MCP remain unfinished.

Define operations for import, annotate, search, fetch memory, fetch region, export, and remove. Return stable IDs, model/index revisions, evidence provenance, coordinates, and explicit errors.

- Use the Python implementation as the initial behavior reference.
- The initial transport is local subprocess pipes, without an HTTP server. Connect the native client first; add an MCP adapter with explicit grants. Add another transport only if the integration requires it.
- One owner coordinates database writes and indexing jobs. Provide cancellation, retries, bounded requests, and predictable state changes.
- Enforce selected-source and collection access in the engine; callers cannot bypass authorization by requesting another record ID.
- Keep image/note contents out of diagnostic logs by default. Treat retrieved text as data, not executable instructions.

**Done when:** a local client can save a note, retrieve matching evidence, export it, and remove it through a tested versioned contract. Begin MCP adapter work here alongside native integration.

## 04 — Native capture, annotations, and command bar · V1

Use SwiftUI/AppKit for a global search panel, annotation view, and small optional capture HUD. Use supported Apple capture and Vision APIs, with the minimum OS version decided before implementation.

- A SeenX capture action records a screenshot and available source context. Snapshot the originating app before the overlay takes focus.
- Watching selected folders also imports ordinary screenshots, but does not magically supply their original app or browser URL.
- Browser URLs require an explicit supported integration and permission. Missing context stays unknown.
- Persist selected-source permissions and handle denial/revocation. Do not require continuous screen recording or automatic file moves.
- Support text selection, pins, region notes, export, and accessible keyboard/touch-equivalent interactions.

**Done when:** take a real screenshot → highlight → save a thought → use the search shortcut → find it after restart. Check Retina/multi-display coordinates, resized previews, permission denial, canceled capture, file changes, and no-note captures.

## 05 — Read-only MCP + agent evaluation harness · V1, parallel with native UI

MCP is a release capability, not a promise to build a general autonomous agent platform.

- Expose compact search results and explicit memory/region fetch through the same engine used by human search.
- Return original/cropped images where requested, selected text, notes, source identifiers, and coordinates. Vector values are an internal retrieval mechanism, not the main assistant payload.
- Start with a local stdio client. Verify actual installation and compatibility. Other transports or cloud-only clients require their own secure integration work.
- Enforce source/collection grants, result bounds, crop bounds, and revocation. No arbitrary filesystem browsing, shell execution, or automatic note edits in the initial bridge.
- Build an evaluation harness: realistic requests, expected memory/region/note IDs, source-grounding checks, no-match cases, malformed calls, and access-denied scenarios.
- Keep an audit of which record IDs were returned without unnecessarily logging sensitive content. A cloud-backed client receiving a result is a separate data-sharing event.

**Done when:** one supported assistant finds the intended screenshot and fetches the correct highlight, note, and original evidence. Revoked records are inaccessible to future requests. Test prompts embedded in images/notes as untrusted data. The external client supplies the agent runtime.

## 06 — Portable library backup and restore · V1 durability

- Offer a deliberate Transfer my library flow for all or selected collections. This moves seenX-managed memories/context, not an entire operating-system installation.
- Complete-library archives include selected image originals and their context. Context-only exports carry notes, selected text, coordinates, IDs/hashes, relationships, and source history; originals need to exist on or be relinked from the destination.
- Preserve stable asset/revision identities, annotation targets, and typed relationships in a versioned manifest. Selected exports must not silently include unrelated private content to fill relationship edges.
- Create a consistent snapshot. Validate content hashes and completeness before marking a backup successful. Indexes/thumbnails are optional derived data; reuse only compatible model/index revisions and rebuild the rest without losing annotations.
- Offer optional passphrase-protected archives through a maintained authenticated-encryption format/library selected during implementation. Protect metadata as well as images. Do not depend solely on an old-Mac-only key; explain unrecoverable-passphrase behavior before use.
- Exclude assistant credentials, tokens, active grants, and machine-specific source permissions. Reconnect external locations and authorize assistants on the destination.
- Validate archive paths, schema versions, missing/corrupt files, and relation targets before importing. Restore to a fresh library or show an explicit merge/conflict preview. Never silently overwrite newer notes; a failed/canceled restore leaves existing data intact.

**Done when:** export an annotated collection from one Mac, restore it into a fresh library on another, and verify image bytes, notes, selected text, aligned highlights, and relationships. Test context-only relinking, missing originals, duplicate IDs, schema migration, incompatible indexes, and encrypted-archive recovery. The website's single-memory JSON export does not implement these archive capabilities.

## 07 — Production migration and desktop beta · V1 release gate

- Integrate catalog, indexing, ranking, and access behavior into the Swift app in small measured slices behind the shared contract.
- Reuse Python datasets, model revisions, preprocessing, and result fixtures; record numeric tolerances and regression results.
- Select a local model runtime after compatibility and packaging checks. Core ML/ONNX are candidates, not implemented dependencies.
- Ship without asking users to install Python; retain Python as the evaluation reference.
- Verify offline operation after model downloads, migration/recovery, interrupted indexing, source removal, derived-index deletion, exports, access revocation, and resource use.
- Complete signing/notarization, clean-machine installation, licensing, and the supported assistant setup.

**Done when:** a clean Mac install completes the real capture-to-assistant loop and verified library restore on a second Mac. Release notes distinguish available behavior from later ideas. No dates are promised until these checks are demonstrated.

## Later scope

Continuous multi-device sync, concurrent-note conflict handling, PDFs and bookmarks as complete annotated memory sources, additional app/browser capture integrations, richer organization, automatic entity/relationship suggestions, and team deployments. Existing PDF-reading experiments remain useful; they do not establish a finished PDF product. Add inference only when evaluation shows improvement over explicit relationships and hybrid search.

## Immediate next step

Design and implement explicit import/write operations for the separate native capture library, preserving notes, OCR boxes, highlight targets, and original bytes. Then connect the main launcher to the shared catalog. The optional native catalog browser already exercises the version-1 search/fetch contract. Evaluate retrieval with labeled queries, and measure lexical and visual behavior before choosing catalog fusion or semantic note embeddings. Add source/collection grants before exposing MCP access.

See [architecture](docs/architecture.md), [the Python walkthrough](python/README.md), and [the public website roadmap](https://seenx-lovat.vercel.app/docs/roadmap).
