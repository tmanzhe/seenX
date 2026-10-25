# seenX architecture

## Product boundary

seenX is a local visual memory for screenshots, saved images, selected text, and human notes. A person searches through a native command bar; a compatible assistant searches through a read-only MCP bridge. Both interfaces retrieve the same evidence from one engine.

The hosted website is a separate static preview. It never becomes the user's local database or a public endpoint for their personal files.

## Current versus planned

| Layer | Exists today | Planned work |
| --- | --- | --- |
| Website | Next.js/React/TypeScript, sample capture, authored text boxes, spatial annotations, localStorage, JSON export | Maintain truthful product/docs copy and demo behavior |
| Python prototype | Image/PDF reading, Vision OCR strings, literal search, CLIP vectors, rank fusion, SQLite cache, diagnostics | Durable memory catalog, OCR boxes, notes, typed links, FTS5, semantic note retrieval, local engine contract |
| Native Mac app | Documentation only | SwiftUI/AppKit command bar and capture HUD; ScreenCaptureKit, Vision, source permissions |
| Rust core | Dependency-free scaffold | Gradual migration of proven storage, indexing, retrieval, and access logic |
| Assistant bridge | Website illustration and export only | Opt-in, bounded read-only MCP retrieval; client integration/evaluation |

## Target stack and why

- **SQLite is the planned catalog:** persistent records, notes, regions, revisions, collections, access grants, migrations, and indexing state.
- **FTS5 provides exact text retrieval:** OCR, selected text, identifiers, names, and human notes.
- **Local embeddings provide semantic retrieval:** image/text encoders find visual similarity; a separately evaluated text encoder can retrieve note paraphrases.
- **Vector search can remain embedded:** evaluate sqlite-vec against exact scanning. SQLite and vector retrieval are complementary, not alternative product directions. No vector extension is installed in the production core today.
- **Python is the development reference:** existing code proves behavior before a port. A bounded local service can connect prototype clients; FastAPI is a candidate, not an existing server.
- **SwiftUI/AppKit own native interaction:** capture, hotkeys, floating panels, platform permissions, OCR adapters, and annotations.
- **Rust is the production engine target:** small measured migrations behind stable contracts, without a required Python runtime for users. Swift/Rust bindings and local inference runtimes are evaluated at their first integration.
- **MCP is the assistant interface:** first-release scope, not a second independent search system or an autonomous agent framework.

## Intended data flow

```text
SeenX capture or selected-source import
  → normalize image orientation + assign immutable asset revision
  → metadata + OCR text/boxes + local embeddings
  → SQLite catalog + text/vector indexes + typed relationships
  → shared retrieval and authorization boundary
      → native command bar / annotation view
      → read-only MCP search / memory fetch / region fetch
```

Capture and note saving should not block on embedding inference. Use bounded background jobs for derived data, explicit states/retries, and a consistent owner for database writes. Note edits refresh the relevant text/vector representations; unrelated model spaces are never compared directly.

## Memory schema

| Record | Responsibility |
| --- | --- |
| Asset + revision | Stable identity, immutable pixel version/hash, orientation, dimensions, source reference |
| Capture/source | Available capture time, import path, originating app or URL when explicitly collected |
| OCR observation | Recognized text, bounding box/range, OCR configuration/revision, provenance |
| Annotation | Human note, optional selected text, whole-image/point/region target, image revision |
| Collection/tag/entity | Explicit organization and optional subjects without a mandatory taxonomy |
| Relationship/assertion | Typed subject/predicate/object with evidence origin and confirmation state |
| Embedding | Associated record/revision, model/preprocessing revision, dimensions, vector space |
| Grant + job | Authorized sources/collections and incremental indexing/recovery state |

Image bytes and thumbnails live in app-managed files; SQLite links their records. Newly captured images can be owned by the app. Imported originals remain untouched. If an imported file changes, create a new revision rather than silently attaching old notes to different pixels. Decide snapshot retention deliberately so annotations can preserve their original evidence.

Use normalized top-left coordinates over the full orientation-corrected image. Convert Apple Vision's coordinate convention at the adapter boundary; screen points, backing pixels, crops, and letterboxed previews must not be conflated. Exports identify the reference image/version and dimensions as well as normalized targets and pixel bounds.

## Lightweight ontology in V1

The ontology is a small schema of meaningful types and relations, stored in SQLite—not a requirement for a separate graph database.

```text
Annotation --refers_to--> Region --part_of--> AssetRevision
AssetRevision --revision_of--> Asset --member_of--> Collection
Asset --captured_from--> Source
Annotation --quotes--> TextObservation
```

These links let an assistant request the exact button, quote, or source a note concerns. Explicit user assertions, imported/system facts, and model-proposed associations are distinguishable. Store provenance and confirmation state. A named place in a note does not establish where the screenshot was captured. Correcting/removing evidence must update dependent relationships and indexes.

Automatic entity extraction, broad knowledge graphs, and speculative associations are later experiments. Keep them only if measured retrieval improves without unacceptable false links or correction effort.

## Search and evaluation

Retrieve candidates from FTS5, compatible image/text vectors, and separately evaluated note embeddings. Combine ranked lists rather than adding incomparable raw scores. Apply access grants and strict filters throughout candidate retrieval/fetch. Return matched text, annotation IDs, source IDs, and method evidence alongside ranked results.

Keep a labeled dataset with exact phrases, visual descriptions, note paraphrases, region-specific requests, and no-match examples. Pin model versions and preprocessing. Measure top-k quality, false matches, indexing/warm-query costs, and memory/storage; cosine scores are not confidence percentages.

## Assistant bridge and harness

MCP ships in V1. Build it alongside the native interface once the shared memory contract exists; it does not need to wait for the complete Rust migration.

The initial surface supports bounded search, explicit memory fetch, and region fetch. Names/wire schemas remain proposed. Search returns compact references; fetching supplies authorized images/crops, selected text, human notes, coordinates, and source evidence. The external client supplies the agent runtime.

Start with a local stdio client. Other transports and cloud-only integrations require their own connection/authentication design. A local server is not automatically reachable by every assistant.

The agent evaluation harness tests search → select → fetch against expected record/annotation IDs, coordinate/source grounding, no-match handling, malformed calls, and access denial. Treat content inside notes/images as untrusted retrieved data, not privileged instructions. No arbitrary file access, command execution, or automatic edits are part of the first bridge.

Revoke access at the engine boundary, including direct record fetches. Record returned IDs without logging unnecessary content. Local indexing and limited sharing do not imply that content already returned to a cloud client remains local or can be recalled.

## Capture metadata and permissions

A SeenX-owned capture can snapshot the originating application before its overlay gains focus. Browser URLs need an explicit supported integration and permission. A watched-folder import generally cannot establish the original app/URL by itself. Missing context stays unknown.

Source permissions, capture permissions, and assistant collection grants are separate. The product does not require continuous recording, automatic file relocation, universal device access, or a heavy library dashboard.

## Delivery sequence

Follow [the implementation roadmap](../plan.md): durable memory/ontology → real OCR and hybrid vectors → shared local contract → native capture/search and MCP in parallel → measured Rust migration and release verification. Python remains the evaluation reference. No dates, completed security audit, encrypted catalog, signed Mac release, or universal assistant compatibility are claimed today.

## Primary technical references

- [SQLite application use cases](https://www.sqlite.org/whentouse.html), [FTS5](https://www.sqlite.org/fts5.html), and [sqlite-vec](https://alexgarcia.xyz/sqlite-vec/).
- [Apple ScreenCaptureKit](https://developer.apple.com/documentation/screencapturekit/scscreenshotmanager) and [Vision](https://developer.apple.com/documentation/vision).
- [MCP transports](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports).
- [UniFFI Swift/Rust bindings](https://mozilla.github.io/uniffi-rs/latest/) as an integration candidate.
