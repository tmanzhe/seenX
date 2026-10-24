# seenX architecture direction

## Development path

Python learning and proof of concept → measured behavior → Rust implementation → later SwiftUI and agent interfaces.

The website and Rust scaffold exist. Python experiments, indexing, inference, and desktop integration are pending.

## Responsibilities

| Component | Responsibility |
| --- | --- |
| [Python experiments](../experiments/README.md) | Learn OCR, embeddings, metadata, hybrid retrieval, and ontology; evaluate reproducibly |
| [Rust core](../crates/seenx-core/README.md) | Production catalog, indexing, retrieval, ranking, and evidence |
| [Website](../apps/web/README.md) | Product explanation, learning guides, and sample interaction preview |
| [macOS app](../apps/macos/README.md) | Later SwiftUI presentation, permissions, previews, and platform adapters |

## Production target

Rust orchestrates the pipeline without requiring Python. Native model runtimes and OS adapters may still be dependencies; not every operation must be implemented in pure Rust. Select runtimes after testing local inference, model compatibility, and preprocessing parity. SQLite is a storage candidate; specific schemas and libraries remain undecided.

## Data flow and evidence

Selected images → metadata + OCR + embeddings → local catalog/indexes → retrieval and ranking → results with source evidence.

An optional ontology defines concepts and relationships. Recorded metadata, user-confirmed associations, and model suggestions remain distinguishable. Store provenance and confirmation status; missing metadata stays unknown. Corrections and source deletion must propagate to derived records.

## Python-to-Rust handoff

Use the same dataset manifests, labeled queries, model revision, and preprocessing. Compare retrieval and numeric results with documented tolerances, then measure resource use. Python remains a learning and evaluation reference rather than a shipped backend.

## Later interfaces

A Rust CLI can validate retrieval before SwiftUI. A read-only MCP adapter could expose selected files and evidence to agents after the engine works. A client's forwarding to remote models is a separate privacy boundary.

See the [plan](../plan.md). Publication, licensing, distribution, and donations remain future work.
