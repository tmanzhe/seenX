# seenX

A local-first image search application for macOS, designed to find screenshots and saved images using visible text and natural-language descriptions.

**Status:** early development. Application functionality is not implemented yet.

Planned capabilities:

- Search text extracted from screenshots with on-device OCR.
- Retrieve images by description using local image and text embeddings.
- Combine keyword and semantic search with a native macOS interface.
- Keep selected folders indexed as files change.

The initial prototype will use Python and SQLite. The intended native architecture uses SwiftUI for the interface and a reusable Rust indexing and retrieval engine.
