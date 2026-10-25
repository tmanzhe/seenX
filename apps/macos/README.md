# seenX macOS app

**Status:** documentation only; there is no native application implementation or downloadable Mac build.

## V1 responsibilities

- SwiftUI/AppKit global search command bar and lightweight floating capture HUD.
- A SeenX capture action using supported ScreenCaptureKit APIs, plus import/watch access to deliberately selected locations.
- Apple Vision OCR adapters that preserve text and locations, after image-orientation normalization.
- Whole-image notes, exact text highlights, pins, and region annotations attached to immutable image revisions.
- Folder/capture permission lifecycle, source inspection, export, and clear assistant-sharing controls.
- Active-app and browser URL metadata only when a supported integration and permissions provide it; watched files alone do not establish those details.

The command bar and annotation UI consume the same memory/search contract as the V1 MCP bridge. A full library dashboard is not a first-release prerequisite.

## Implementation path

Start with the existing Python engine and a bounded local contract so a real screenshot can be captured, annotated, persisted, and retrieved. Native UI and the read-only MCP adapter can develop alongside one another once that contract exists. Gradually replace proven engine behavior with Rust; do not require users to install Python in the intended production release.

Swift/Rust bindings, model-runtime packaging, minimum supported macOS version, and the actual app/service boundary are selected during the first working integration. Full Xcode is required for native implementation. Existing web demo code is an interaction reference, not a substitute for native screen/file permissions.

**First native acceptance:** real capture → highlight → optional note → save → restart → search → assistant retrieves the same authorized image/region and note. Check display scaling, resized previews, permission denial, missing originals, and source revocation.

See [architecture](../../docs/architecture.md) and [the implementation roadmap](../../plan.md).
