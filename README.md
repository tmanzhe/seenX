# seenX

A local-first image search application for macOS, designed to find screenshots and saved images using visible text and natural-language descriptions.

**Status:** a Next.js product/docs site, dependency-free Rust library scaffold, and a Python search command with text, visual, and hybrid modes are available. Python includes optional macOS OCR, local extraction caching, and CLIP image embeddings. Desktop integration and the native macOS app are not implemented yet. Start with the [Python walkthrough](python/README.md) to follow the current build step by step.

Planned capabilities:

- Search text extracted from screenshots with on-device OCR.
- Retrieve images by description using local image and text embeddings.
- Filter results using available location, date, and file metadata.
- Combine keyword and semantic search with a native macOS interface.
- Keep selected folders indexed as files change.

The development path is Python first: learn and prototype OCR, embeddings, metadata, hybrid retrieval, and ontology. Measure the results, connect a local interface/API when retrieval is useful, then gradually implement proven behavior in Rust behind a stable interface. Production should run without Python, using native inference libraries where needed. SwiftUI is a later interface, not the current focus.

## Repository structure

| Location | Responsibility |
| --- | --- |
| [apps/macos](apps/macos/README.md) | Native interface and macOS integrations |
| [apps/web](apps/web/README.md) | Next.js product website, documentation, and sample-library preview |
| [crates/seenx-core](crates/seenx-core/README.md) | Reusable Rust catalog, indexing, and retrieval engine |
| [Python engine](python/README.md) | Python investigations of embeddings and retrieval quality |
| [docs/architecture.md](docs/architecture.md) | Component boundaries and intended data flow |

## Local development

For Python, start at the repository root:

```sh
uv sync --project python --all-extras
uv run --project python seenx-search practice-images --mode hybrid --ocr --cache --query "basketball"
```

No manual environment activation is needed. See the [Python README](python/README.md) for setup, caching, logging, search limitations, and the detailed learning walkthrough.

Use Node.js 20.9 or newer for the website, and Rust 1.85 or newer for the core. From the repository root:

```sh
npm ci
npm run dev
```

Open the local URL printed by Next.js. The sample preview uses authored records and keyword matching; it does not search your files or run an embedding model.

```sh
npm run typecheck
npm run build
cargo check --offline --workspace
```

The production web build is exported to `apps/web/out/`. The root npm workspace manages the website, and the Cargo workspace manages the Rust core. Python has its own environment and setup instructions in the [Python walkthrough](python/README.md). Xcode setup is deferred.

## Release direction

The intended release is free and open source, supported by optional donations. The [repository is public on GitHub](https://github.com/tmanzhe/seenX), but no open-source license has been selected and no donation destination is configured. There is no checkout or desktop download yet.

A read-only CLI or MCP adapter for self-hosted agents is a future possibility after local retrieval works.

See [the implementation plan](plan.md) for the project purpose, roadmap, and next step.
