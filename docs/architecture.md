# seenX architecture direction

## Development path

Python learning and proof of concept → measured retrieval → local interface/API prototype → gradual Rust implementation → native macOS and agent interfaces.

The website and Rust scaffold exist. Python supports image/PDF reading, local macOS OCR, keyword search, optional SQLite extraction caching, and a CLIP visual-search experiment. Desktop integration is pending.

First make retrieval useful in Python. Then a local API, potentially FastAPI, can connect a local interface to the Python engine so we can try the whole workflow. There is no Python API server yet. The public product website remains separate: a hosted website can't simply read a user's local folders. We need a deliberate local integration before connecting it to personal files.

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

Use the same dataset manifests, labeled queries, model revision, and preprocessing. Compare retrieval and numeric results with documented tolerances, then measure resource use. Migrate small responsibilities behind a stable interface rather than rewriting the whole app at once. Python remains a learning and evaluation reference rather than a required shipped backend.

## Later interfaces

A Rust CLI can validate retrieval before SwiftUI. A read-only MCP adapter could expose selected files and evidence to agents after the engine works. A client's forwarding to remote models is a separate privacy boundary.

See the [plan](../plan.md). The source repository is public; licensing, desktop distribution, and donations remain future work.
