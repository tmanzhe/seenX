# seenX — product and implementation roadmap

## Product contract

A local visual memory for the things you save and the thoughts you attach to them. One memory engine serves a person through a lightweight search interface and an authorized assistant through MCP.

**V1 loop:** capture → recognize text → highlight/pin → optional note → save → search → retrieve the same evidence through a compatible assistant.

This plan supersedes the earlier sequence that put a broad ontology experiment before annotations and deferred assistant access indefinitely. A bounded, explicit ontology belongs in the memory model; automatic relationship extraction is evaluated later. MCP is in V1 and can be developed in parallel with the native interface once engine contracts exist.

## Current implementation

- **Website:** working authored sample capture, image results, text selection, pins/regions, notes, browser persistence, Command/Ctrl K, and JSON context export. No real image access, OCR, vector inference, or assistant connection.
- **Python:** image/PDF reading, macOS Vision OCR strings, literal text search, CLIP visual vectors, hybrid rank fusion, optional SQLite extraction/vector cache, diagnostics, and tests.
- **Rust:** dependency-free library scaffold only.
- **Native app/API/MCP:** not implemented.
- **FTS5, durable annotation catalog, OCR coordinates, semantic note embeddings, and sqlite-vec:** not implemented.

## 01 — Durable local memory + lightweight ontology · NEXT

Build a versioned SQLite catalog that is separate from the disposable extraction cache.

- Stable asset and immutable revision IDs; content hash, normalized orientation, dimensions, source references, and thumbnails.
- Whole-image notes, selected text, point targets, and rectangular regions using normalized top-left coordinates.
- Text observations with provenance; user notes remain separate from OCR and model descriptions.
- A small typed relationship model: annotation refers to region; region belongs to image revision; image belongs to collection; capture came from source. Include tags and optional user-defined subjects without requiring automatic inference.
- Store assertion provenance and confirmation state. Imported evidence, user labels, and proposed model associations are different facts.
- Schema migrations, save/edit/remove, export, and deliberate handling of missing or changed originals. Preserve imported originals; keep capture snapshots/annotated revisions stable.

**Done when:** import one real screenshot, save a region note, restart, and recover the original image revision, selected text, note, and aligned location. Update/delete operations are transactional and repeatable.

## 02 — Real OCR and hybrid retrieval · V1

- Extend Vision OCR to retain text observations and word/range locations, not just a combined string.
- Normalize Vision coordinates, EXIF orientation, screen points, and image pixels into the shared image coordinate system.
- Add SQLite FTS5 for OCR, highlighted text, and user notes; preserve exact identifier/phrase retrieval.
- Keep compatible image/text encoders for visual similarity. Evaluate a separate text encoder for paraphrases of notes; never compare unrelated embedding spaces directly.
- Prototype sqlite-vec and compare it with exact vector scanning. Final library/runtime selection follows retrieval, packaging, and resource measurements.
- Fuse ranked exact/visual/note results, then preserve source evidence and explicit access/filter constraints.
- Incrementally update indexes after note edits or source changes. Pin model revisions and invalidate stale embeddings deliberately.

**Done when:** a labeled dataset of roughly 50–200 images covers OCR phrases, visual descriptions, note paraphrases, region intent, and genuine no-match queries. Record top-k quality, false matches, indexing time, warm latency, memory, storage, hardware, and model revisions. Reproduce offline after model installation. No accuracy target is claimed before measurement.

## 03 — Shared local engine contract · V1

Define operations for import, annotate, search, fetch memory, fetch region, export, and remove. Return stable IDs, model/index revisions, evidence provenance, coordinates, and explicit errors.

- Use the Python implementation as the initial behavior reference.
- A small local service, with FastAPI as a prototype candidate, may connect the first native/MCP clients. It is not the public website backend.
- One owner coordinates database writes and indexing jobs. Provide cancellation, retries, bounded requests, and predictable state changes.
- Enforce selected-source and collection access in the engine; callers cannot bypass authorization by requesting another record ID.
- Keep image/note contents out of diagnostic logs by default. Treat retrieved text as data, not executable instructions.

**Done when:** a local client can save a note, retrieve matching evidence, export it, and remove it through a tested versioned contract. Begin MCP adapter work here; do not wait for the Rust migration.

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

## 06 — Production migration and desktop beta · V1 release gate

- Gradually implement measured catalog, indexing, ranking, and access behavior in Rust behind the same contract.
- Reuse Python datasets, model revisions, preprocessing, and result fixtures; record numeric tolerances and regression results.
- Select a local model runtime after compatibility and packaging checks. Core ML/ONNX and a Swift/Rust binding such as UniFFI are candidates, not implemented dependencies.
- Ship without asking users to install Python; retain Python as the evaluation reference.
- Verify offline operation after model downloads, migration/recovery, interrupted indexing, source removal, derived-index deletion, exports, access revocation, and resource use.
- Complete signing/notarization, clean-machine installation, licensing, and the supported assistant setup.

**Done when:** a clean Mac install completes the real capture-to-assistant loop. Release notes distinguish available behavior from later ideas. No dates are promised until these checks are demonstrated.

## Later scope

PDFs and bookmarks as complete annotated memory sources, additional app/browser capture integrations, richer organization, automatic entity/relationship suggestions, and team deployments. Existing PDF-reading experiments remain useful; they do not establish a finished PDF product. Add inference only when evaluation shows improvement over explicit relationships and hybrid search.

## Immediate next step

Define the first asset/revision/annotation schema and extend the existing Python Vision adapter to return text boxes. Import one real screenshot, save one note against a region in SQLite, restart, and retrieve it through a small local command. This creates the foundation for both native capture and MCP without starting a full rewrite.

See [architecture](docs/architecture.md), [the Python walkthrough](python/README.md), and [the public website roadmap](https://seenx-lovat.vercel.app/docs/roadmap).
