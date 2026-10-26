# seenX architecture

## Product boundary

seenX is a local visual memory for screenshots, saved images, selected text, and human notes. A person searches through a native command bar; a compatible assistant searches through a read-only MCP bridge. Both interfaces retrieve the same evidence from one engine.

The hosted website is a separate static preview. It never becomes the user's local database or a public endpoint for their personal files.

## Current versus planned

| Layer | Exists today | Planned work |
| --- | --- | --- |
| Website | Next.js/React/TypeScript, sample capture, authored text boxes, spatial annotations, localStorage, JSON export | Maintain truthful product/docs copy and demo behavior |
| Python prototype | Image/PDF reading, Vision OCR strings/boxes, literal search, CLIP vectors, rank fusion, SQLite cache, diagnostics, versioned memory catalog and OCR quote links | Word/range selection, richer catalog relationships/collections, FTS5, semantic note retrieval, local engine contract, portable export |
| Native Mac app | Initial SwiftUI/AppKit menu-bar app: translucent search, global shortcuts, system region capture, Vision text highlights, notes, separate local development library | Shared-engine integration, ScreenCaptureKit adapter, source permissions, production distribution |
| Assistant bridge | Website illustration and export only | Opt-in, bounded read-only MCP retrieval; client integration/evaluation |

## Target stack and why

- **SQLite is the planned catalog:** persistent records, notes, regions, revisions, collections, access grants, migrations, and indexing state.
- **FTS5 provides exact text retrieval:** OCR, selected text, identifiers, names, and human notes.
- **Local embeddings provide semantic retrieval:** image/text encoders find visual similarity; a separately evaluated text encoder can retrieve note paraphrases.
- **Vector search can remain embedded:** evaluate sqlite-vec against exact scanning. SQLite and vector retrieval are complementary, not alternative product directions. No vector extension is installed in the production core today.
- **Python is the development reference:** existing code proves behavior before a port. A bounded local service can connect prototype clients; FastAPI is a candidate, not an existing server.
- **SwiftUI/AppKit own native interaction:** capture, hotkeys, floating panels, platform permissions, OCR adapters, and annotations.
- **Native engine integration follows measured behavior:** connect the Swift app to proven catalog and retrieval operations behind stable contracts, using the Python implementation as the evaluation reference.
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

The first Python catalog implements those ownership links with SQLite foreign keys and retains exact imported bytes as content-addressed objects. Dimensions and annotation coordinates refer to the EXIF-corrected display; stored bytes keep their original orientation metadata. `seenx-memory` exposes import, whole-image/point/region annotation, revision-aware fetch, edit, and logical removal. It checks snapshot hashes on fetch and is independent of the retrieval cache. See [the catalog lesson](../python/docs/catalog.md) for retention limits and remaining work. Current removal retains object files; garbage collection, complete-library export, and access-controlled API fetch aren't implemented yet.

Catalog version 2 adds immutable OCR runs and observations. The adapter converts Vision's bottom-left boxes into normalized top-left coordinates after EXIF correction. An annotation may quote an observation only from its own revision; the selected text retains OCR/unverified provenance. A changed recognition configuration creates a new run instead of overwriting linked evidence. The additive version-1 migration, OCR writes, and quote creation are transactional. See [the OCR observation lesson](../python/docs/ocr-observations.md).

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

MCP ships in V1. Build it alongside the native interface once the shared memory contract exists.

The initial surface supports bounded search, explicit memory fetch, and region fetch. Names/wire schemas remain proposed. Search returns compact references; fetching supplies authorized images/crops, selected text, human notes, coordinates, and source evidence. The external client supplies the agent runtime.

Start with a local stdio client. Other transports and cloud-only integrations require their own connection/authentication design. A local server is not automatically reachable by every assistant.

The agent evaluation harness tests search → select → fetch against expected record/annotation IDs, coordinate/source grounding, no-match handling, malformed calls, and access denial. Treat content inside notes/images as untrusted retrieved data, not privileged instructions. No arbitrary file access, command execution, or automatic edits are part of the first bridge.

Revoke access at the engine boundary, including direct record fetches. Record returned IDs without logging unnecessary content. Local indexing and limited sharing do not imply that content already returned to a cloud client remains local or can be recalled.

## Capture metadata and permissions

A SeenX-owned capture can snapshot the originating application before its overlay gains focus. Browser URLs need an explicit supported integration and permission. A watched-folder import generally cannot establish the original app/URL by itself. Missing context stays unknown.

Source permissions, capture permissions, and assistant collection grants are separate. The product does not require continuous recording, automatic file relocation, universal device access, or a heavy library dashboard.

## Portable library contract · V1

Backup/restore carries durable meaning across computers. A complete-library archive includes selected originals; a context-only export requires relinking the matching originals. Neither is a full laptop/OS migration tool.

- Use a versioned manifest with stable asset/revision IDs, content hashes, normalized dimensions/coordinates, selected text, notes, collections, typed relationships, and source history.
- Snapshot database records and referenced images consistently. Check completeness; retain evidence of missing originals instead of silently calling an incomplete export complete.
- Preserve relationship closure or explicit unresolved references without adding unrelated private images to a selected export. Do not use absolute paths as portable identity.
- Indexes and thumbnails are derived/optional. Check model/index versions before reuse and rebuild incompatible indexes without changing human notes or their source revisions.
- Plan optional passphrase protection using a maintained authenticated-encryption library/format, including manifest and metadata protection. Avoid a transfer format that can be opened only with a key on the old machine. No archive encryption is implemented or audited today.
- Exclude assistant credentials, tokens, active grants, and machine-specific permissions; reauthorize clients and reconnect external locations on the destination.
- Validate archive paths, checksums, schemas, relation targets, missing assets, and duplicates before writing. Use a fresh-library restore or explicit merge preview, safe cancellation, and schema migration; never silently replace newer notes.

The V1 release check restores the same annotated library onto a second Mac. Continuous multi-device sync is later scope with separate conflict/deletion semantics. The existing website exports a single sample record as JSON; it cannot produce or restore a complete library archive.

## Delivery sequence

Follow [the implementation roadmap](../plan.md): durable memory/ontology → real OCR and hybrid vectors → shared local contract → native capture/search and MCP in parallel → portable-library restore → native engine integration and release verification. Python remains the evaluation reference. No dates, completed security audit, encrypted catalog, signed Mac release, or universal assistant compatibility are claimed today.

## Primary technical references

- [SQLite application use cases](https://www.sqlite.org/whentouse.html), [FTS5](https://www.sqlite.org/fts5.html), and [sqlite-vec](https://alexgarcia.xyz/sqlite-vec/).
- [Apple ScreenCaptureKit](https://developer.apple.com/documentation/screencapturekit/scscreenshotmanager) and [Vision](https://developer.apple.com/documentation/vision).
- [MCP transports](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports).
