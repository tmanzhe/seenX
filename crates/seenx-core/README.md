# seenX core

**Status:** the dependency-free Rust library scaffold builds. Cataloging, indexing, and retrieval are not implemented yet.

This component will contain a reusable Rust engine for:

- The persistent image catalog and indexing state.
- Indexing decisions, work coordination, and incremental updates.
- Keyword and semantic retrieval, metadata constraints, and ranking.

Platform-specific UI, permissions, and Apple APIs belong to the macOS app and its adapters. Keeping that boundary explicit will allow the engine to be exercised independently.

The root `Cargo.toml` defines the workspace. This directory's `Cargo.toml` defines the library package, and `src/lib.rs` is its source entry point. The scaffold deliberately contains no application functions or third-party dependencies.

From the repository root, check it offline:

```sh
cargo check --offline --workspace
```

Feature implementation follows Python learning and measured proof-of-concept results. Then port small slices using the same evaluation queries. Rust owns production retrieval without a required Python interpreter, and may call native inference libraries or platform adapters. Package publication is disabled while the release and license are undecided.

See the [architecture](../../docs/architecture.md) and [implementation plan](../../plan.md).
