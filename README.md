# seenX

**Save what matters. Find it by what you remember. Keep the context that makes it yours.**

seenX is a local visual memory for screenshots, saved images, highlights, and the thoughts you attach to them. Search it yourself, or optionally let a compatible AI assistant retrieve selected memories and their context.

The first-release loop is **capture → highlight or pin → add an optional note → save → search → reuse through an assistant**. It is not limited to coding: visual references, everyday details, travel ideas, and previous solutions belong in the same personal memory.

## What works today

| Component | Current status |
| --- | --- |
| [Website and docs](apps/web/README.md) | Working sample capture, image search, text highlights, point/region notes, browser persistence, and JSON context export. [Live website](https://seenx-lovat.vercel.app). |
| [Python engine](python/README.md) | Image/PDF reading, optional macOS OCR, text/visual/hybrid search, caching, diagnostics, and an initial durable image/revision/region-note catalog with CLI import, edit, fetch, and removal. |
| [Mac application](apps/macos/README.md) | Native capture, highlights, notes, local search, and an optional Python catalog connection. Requires macOS 14+ and signing setup. |

The website uses authored samples and keyword matching. It does not read personal files, run semantic models, perform real OCR, or connect an assistant. Python has a separate versioned memory catalog with FTS5 search over notes, selections, and saved OCR boxes. Its read-only MCP server offers search, fetch, and image/region payload creation without calling a model. Follow [the catalog lesson](python/docs/catalog.md) to import an image and save a region note that survives restart.

## V1 direction

- A global search command bar and a small optional capture HUD.
- Screenshots and images from deliberately chosen sources; imported originals stay put.
- Editable whole-image notes, selected text, pins, and highlighted regions linked to an immutable image revision.
- A **SQLite catalog + FTS5 exact search + local vector retrieval**. Evaluate sqlite-vec against the existing exact-scan baseline before choosing the shipping vector index.
- A lightweight ontology: explicit, typed relationships between images, regions, notes, collections, and sources. Inferred suggestions stay separate from user-confirmed facts.
- An opt-in, read-only **MCP bridge in V1**, using the same search engine as the human interface.
- Portable library backup/restore in V1: complete archives with originals or context-only exports, preserved notes/highlights/relationships, optional passphrase protection, and verified transfer to another Mac. Continuous sync is later scope.
- An agent evaluation harness to test retrieving the right evidence. The connected client runs the agent; seenX supplies memory.

Local storage and search are separate from sharing results: content returned to a cloud-backed assistant leaves the device. Active-app or URL capture needs a supported integration and permissions; it cannot reliably be inferred from a file appearing in a folder.

## Roadmap

1. **Durable local memory:** SQLite schema/migrations, asset revisions, annotations, typed relationships, export, and removal.
2. **Real searchable evidence:** OCR boxes, FTS5, visual vectors, semantic note retrieval, and reproducible ranking evaluation.
3. **Shared local engine contract:** import, annotate, search, fetch memory/region, export, remove, and indexing jobs.
4. **Native capture and search:** SwiftUI/AppKit command bar, capture HUD, and platform adapters.
5. **MCP and agent evaluations:** build alongside the native UI once shared contracts exist.
6. **Portable library and restore:** versioned complete/context-only archives, relinking, optional encryption, and new-laptop restore checks; reconnect access deliberately.
7. **Production handoff and beta:** verify model/runtime packaging, offline behavior, permissions, and distribution. Use the working Swift app and Python reference to guide engine integration.

Python supports [complete and context-only library archives](python/docs/library-archive.md). The website exports single-memory JSON, not a backup of your real images or laptop.

The complete milestones and completion criteria are in [the implementation plan](plan.md). [Architecture](docs/architecture.md) explains SQLite, vectors, the ontology, and component boundaries. PDFs/bookmarks as complete memory sources, automatic entity inference, team deployment, and a large organizing dashboard are later scope; existing PDF-reading experiments remain available.

## Repository structure

| Location | Responsibility |
| --- | --- |
| [apps/web](apps/web/README.md) | Product website, public roadmap, sample interaction, and documentation |
| [Python engine](python/README.md) | Current prototype and evaluation reference |
| [apps/macos](apps/macos/README.md) | Planned native capture, permissions, search, and annotation interface |
| [docs/architecture.md](docs/architecture.md) | Stack decisions and implementation boundaries |
| [plan.md](plan.md) | Ordered milestones, acceptance criteria, and immediate next step |

## Quickstart

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run from the repository root on Linux or macOS:

```sh
uv sync --project python --locked --extra mcp
uv run --project python --extra mcp python -m seenx.demo
```

The demo makes a synthetic image in a temporary library, saves a region note, then searches and fetches it through a local MCP subprocess. It checks crop/full-image payload pixels and revoked access, then removes the library. No API keys, paid APIs, OCR, model downloads, or database server are needed. Expect `PASS: offline demo; no model calls; temporary library removed.`

For your own files and optional visual search, follow the [Python walkthrough](python/README.md).

## Development

For the website, use Node.js 24 (also recorded in `.node-version`):

```sh
npm ci
npm run dev
npm run typecheck
npm run build
```

The export is written to `apps/web/out/`. Website notes are browser-local sample data; they are separate from the native library.

For a repeatable container build, run `docker compose up --build` and open <http://127.0.0.1:8080>. See [development and CI](docs/development.md) for the build, checks, and supported platforms, and [the security review](docs/security-review.md) for findings and limits.

The production target does not require users to install Python. Keep Python as the development reference and integrate small tested slices into the native app. Full Xcode setup becomes necessary for native development.

## Website deployment

The `seenx` Vercel project serves <https://seenx-lovat.vercel.app>. Root [vercel.json](vercel.json) builds the npm workspace and publishes the static export. It does not host personal memories, an indexer, or an MCP endpoint.

## Release direction

The [source repository is public](https://github.com/tmanzhe/seenX). The intended release is free/open source with optional support, but an application license, signed native download, and donation destination remain unfinished. Third-party sound notices are included with the web assets. No desktop availability or encrypted-storage audit is claimed.
