# seenX — learning and implementation plan

## Direction

Learn and prototype in Python first. Measure useful behavior, then implement the proven pipeline in Rust. SwiftUI is a later interface, not the current focus. The website and Rust scaffold exist; Python setup and real retrieval are still pending.

## 1. Python semantic-search proof of concept

Start with ten user-selected images and one pretrained compatible image/text encoder. Learn loading, preprocessing, vectors, normalization, and similarity one step at a time. Display the top five results. This is inference, not model training.

Expand to 50–200 images and 10–15 queries with acceptable matches labeled before running the ranking. Record top-five hit rate, indexing time, warm query latency, hardware, dependencies, and exact model revision. Rerun offline after downloads. Keep personal images, model assets, and generated outputs untracked.

## 2. OCR, metadata, and hybrid retrieval in Python

Extract visible text and available metadata. Preserve capture time separately from filesystem timestamps. Compare keyword, visual, and combined retrieval on the same queries. Distinguish strict filters from ranking signals; missing location stays unknown.

Done when expected screenshot phrases and visual descriptions retrieve relevant images with inspectable source evidence and recorded failures.

## 3. Bounded ontology experiment in Python

Use Image, Receipt, Trip, and Place to test whether explicit relationships improve receipt-by-trip searches over the OCR/metadata baseline. Begin with roughly 30–50 suitable images and labeled queries.

Models may propose associations. Store evidence, extraction method, and confirmation status. User corrections update stored knowledge without retraining model weights. Keep suggestions separate from confirmed facts. Review changes to the ontology definitions deliberately.

Done when the comparison shows which relationships help and which introduce errors. Retain useful additions rather than building a general autonomous ontology platform.

## 4. Implement proven behavior in Rust

Port small slices: discovery, catalog, metadata, OCR integration, embeddings, retrieval, and validated ontology behavior. Keep Python as the development reference. Reuse datasets, labels, model revisions, and preprocessing; compare outputs with documented numeric tolerances.

Rust owns production orchestration and retrieval without a required Python interpreter or Python subprocess. Native inference libraries and platform adapters may execute model and OS operations. Validate a viable Rust integration before committing to a prototype-only runtime.

Measure indexing, latency, memory, and storage. Verify offline operation, rescans, file changes, cancellation, source removal, and recovery.

## 5. Interfaces and release

A Rust CLI can exercise real retrieval before desktop integration. SwiftUI later adds windows, folder permissions, and previews. Evaluate a read-only MCP adapter after retrieval works. Packaging, signing, licensing, public source publication, and optional donations follow separately.

## Immediate next step

Select the practice-image folder and set up an isolated Python environment. Load ten images before downloading a model. Explain one concept, make one small change, inspect the output, and review together before expanding.

See the [architecture](docs/architecture.md), [experiments](experiments/README.md), and [README](README.md).
