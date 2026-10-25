# seenX core

**Status:** a dependency-free Rust library scaffold. A persistent catalog, indexing, search, ontology, API, and MCP implementation do not exist in this crate yet.

## Production responsibilities

- SQLite catalog and migrations for assets/revisions, sources, notes, OCR observations, point/region targets, indexing jobs, and collection grants.
- Lightweight ontology: typed relationships with source provenance and explicit assertion/confirmation state.
- FTS5 exact retrieval plus local visual/text vector retrieval and evidence-preserving rank fusion. Evaluate sqlite-vec against exact scanning before selecting a shipping vector index.
- Incremental indexing, model/index revisions, source reconciliation, derived-data deletion, recovery, and export.
- Planned portable-library snapshots/manifests and validated restore, preserving IDs and annotations while excluding machine-specific credentials/grants.
- One retrieval/authorization contract shared by native human search and the read-only V1 MCP bridge.

Platform UI, screenshot capture, OS permissions, and native OCR/model adapters belong to the macOS boundary. Rust owns reusable memory and retrieval logic, not every platform API or model runtime implementation.

## Development path

Use the existing Python implementation as the learning/evaluation reference. Stabilize real memory/annotation operations and local contracts first; begin native and MCP integration without waiting for the entire Rust migration. Port small measured slices using the same model revisions, preprocessing, labeled datasets, and result fixtures. The production target does not require a Python interpreter.

No dependencies or APIs have been selected merely by documenting them here. Packaging, runtime compatibility, Swift bindings, access enforcement, and offline verification need working integration tests.

From the repository root, validate the current scaffold with:

```sh
cargo check --offline --workspace
```

Package publication is disabled while release and licensing decisions are unfinished. See [architecture](../../docs/architecture.md) and [the roadmap](../../plan.md).
