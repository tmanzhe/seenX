# seenX macOS app

**Status:** implementation has not started. This directory contains documentation only.

This component will provide the native SwiftUI application and own its macOS integrations:

- Windows, search interaction, progress, and UI state.
- Folder selection and the lifecycle of file-access permissions.
- Image previews and opening results.
- Platform adapters for metadata extraction, Apple Vision OCR, and file monitoring.

The app will present results supplied by the Rust engine. The integration mechanism will be chosen when the first cross-component operation is implemented.

SwiftUI is deferred while retrieval is learned and prototyped in Python, then implemented in Rust. A native window and folder picker follow a working engine. Full Xcode is needed at that later stage.

See the [architecture](../../docs/architecture.md) and [implementation plan](../../plan.md).
