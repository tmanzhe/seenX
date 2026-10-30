# seenX macOS app

A basic native menu-bar app: a translucent search panel, quick screenshots, and screenshots with text highlights and a note. Built with SwiftUI/AppKit and Apple Vision on macOS 14 or later. Capture and native-library search use Apple frameworks without a Python runtime. The launcher can also connect to an existing Python catalog through the same local Swift client as the optional **Open Python Library…** browser.

The interface follows the seenX Design Proposal with a launcher flow: compact glass search, a thumbnail library and saved-image previews inside the same floating panel, an image-led annotation stage with an inline note, and a first-run permission screen. The default is clear white Liquid Glass with a subtle blue tint, independent of the system appearance. macOS 26+ uses native clear Liquid Glass; macOS 14–25 use a frosted fallback. Reduce Transparency uses opaque surfaces.

## Build and open

With Xcode and an Apple Development or Developer ID Application certificate installed, copy `apps/macos/signing.example.sh` to `apps/macos/signing.local.sh` and fill in your team and signing identity. The local file is ignored by git. You can also set `SEENX_DEVELOPMENT_TEAM` and `SEENX_CODE_SIGN_IDENTITY` in your environment; those values take priority. Use the same identity for debug and release builds.

From the repository root:

```sh
bash apps/macos/build.sh
open apps/macos/.build/app/seenX.app
```

The script requires signing configuration and checks the certificate type and team. It keeps the bundle ID `dev.seenx.native` and has no ad-hoc fallback, so rebuilds keep the same app identity for Screen Recording. It prefers the existing full Xcode installation unless you set `DEVELOPER_DIR`. This is a local build, not a notarized download. Quit the running copy before opening a rebuild.

To run the focused behavior and storage checks:

```sh
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcrun swift test --package-path apps/macos --build-system native
```

## Shortcuts

| Shortcut | Action |
| --- | --- |
| **⌘⇧K** | Toggle the compact search overlay, including while another app has focus |
| **⌘⇧← / → / ↑ / ↓** | Move the visible search overlay 24 points per press; stop at screen edges |
| **⌘K** | Focus search in the current search/library window |
| **⌘Q** while seenX has focus | Fully quit seenX, protecting any unsaved annotation draft |
| **↑ / ↓ / Enter** in search | Select a result and open its saved image/context |
| **⌘⇧=** | Select a screen region, then save it immediately |
| **⌘⇧−** | Select a screen region, then open the highlight/note editor |
| **⌘Enter** in the editor | Commit the pending text highlight; with no pending selection, save the capture |
| **⌘Delete** in the editor | Clear the pending selection, or remove the selected/latest highlight |
| **⌘Z / ⌘⇧Z** | Undo/redo text edits while typing, or highlight changes while the image has focus |
| **Escape** in the launcher | Go back from a preview/library, clear search text, then dismiss the launcher |
| **Escape** during capture/annotation | Cancel screen selection; clear a pending highlight; protect an unsaved draft before discarding |

The screenshot shortcuts refer to the physical `=` and `-` keys on a US keyboard. They use Shift as part of the shortcut, so the visible characters are `+` and `_`. A conflicting shortcut is reported and the menu-bar actions remain available.

The `seenX` menu-bar item provides the same actions, Open Library, Try a sample image, and Quit. An empty launcher offers capture and library commands; use arrows and Enter to run them. Opening a search result or the library navigates within the same panel, with a back button and preserved search context. The compact Actions menu holds secondary commands and the glass-background opacity control. Drag to select a region within one display; Escape cancels. macOS may ask for Screen & System Audio Recording permission; no audio recording is used. Canceling selection does not create a memory.

The app has no Dock icon. To quit without finding its menu-bar item, summon it with **⌘⇧K** and press **⌘Q**, or use **Actions → Quit seenX**. **Actions → Restart seenX** safely relaunches the current app bundle. Hiding the overlay keeps the app running.

## First run

The welcome panel explains screen access before asking macOS for permission. Choose **Allow screen access**, **Try a sample image instead**, or the close button to set up later. The sample is an authored invoice image; it does not access the screen, and enters the library only if you explicitly save it. A denied screen permission can be enabled in System Settings. After a new grant, seenX shows **Permission granted, please relaunch** with a restart button. No capture runs until you relaunch. Search, the library, and sample annotations work without screen access.

If an old ad-hoc build left Screen Recording stuck, quit seenX and run this once, then open the signed app and allow access again:

```sh
tccutil reset ScreenCapture dev.seenx.native
```

Permission checks use `CGPreflightScreenCaptureAccess()` before capture and request access when needed. On macOS 14+, ScreenCaptureKit's `SCScreenshotManager` captures the selected region. The older system screenshot path stays as a fallback; this package still targets macOS 14+. Capture errors are shown, and cancellation saves nothing.

## Highlight and save

1. Capture with **⌘⇧−**.
2. Wait for on-device text recognition. Click a recognized text box or drag across boxes to select text. Selection initially remains pending.
3. Press **⌘Enter** to commit that highlight. Repeat to add more highlights, and optionally write in the floating **Add a thought…** field beside the selection.
4. Press **⌘Enter** with no pending selection to save and close. With no highlights selected, a note-only capture saves on the first press.

Highlights refer to recognized text boxes, not arbitrary painted regions or character-level text ranges. Their coordinates use a normalized top-left origin, so they follow the screenshot when the preview resizes. OCR can miss text; a capture still saves without recognized text. Save failures keep the draft open.

Search matches words in recognized text, notes, and highlights. An empty query lists recent captures. This is local literal search, not semantic/visual retrieval. Open a saved result to inspect the original image and saved context.

Choose **Connect catalog…** in the launcher, select the prepared seenX repository and an existing folder containing `catalog.sqlite3`, then type to search. Up to five catalog evidence hits appear before native matches, labeled with their matched field and provenance; earlier revisions are marked. Return opens the exact saved revision inline, with full-image and saved-region fetch controls. Catalog search uses version-1 FTS5 phrase search through the existing client, with a short typing delay and stale-result protection. Empty queries still show native recents; **Browse Library** shows native captures. **Actions → Disconnect Catalog** ends this session; hiding the launcher keeps it connected. Catalog selection is per session and separate from the optional browser's connection.

## Storage and boundaries

The menu-bar action **Open Python Library…** opens a separate read-only development browser. Click **Connect…**, choose the seenX repository with its prepared Python environment, and then choose an existing Python library folder containing `catalog.sqlite3`. Search saved notes/selections/OCR, select evidence to fetch its exact image, and switch to a saved-region crop. Full-image previews mark the matching target. Helper failures disconnect safely and preserve the typed query; closing the browser closes its connection. See [the step-by-step integration lesson](../../docs/native-engine.md) for setup, limits, tests, and the rationale.

Screenshots and an atomically written `library.json` manifest live in `~/Library/Application Support/seenX Native/`. Restarting the app reloads this library. These files are separate from the Python catalog and the website's sample data. There is no cloud upload, assistant connection, or automatic access to other folders in this slice.

The app captures only after a deliberate capture action. Its panels are hidden during capture. A new capture does not replace an unfinished annotation draft. The opacity slider adjusts only the glass background; text and controls retain full contrast. The annotation image stays opaque so highlights remain readable. Search remembers its position between shortcut toggles. Movement shortcuts are registered only while the launcher is visible, so other apps regain their usual text-selection shortcuts when it is hidden.

## Remaining integration

- Reconcile native capture storage with the catalog through an explicit import/write design preserving originals, OCR, notes, and highlights. Launcher retrieval now uses the existing search/fetch contract; captures are not automatically imported.
- Character-level text selection, editable saved annotations, image import, and library deletion/organization.
- Supported source metadata, source permission management, portable backup/restore, and an opt-in read-only MCP bridge.
- Verify Retina/multi-display selection, permission denial/revocation, shortcut conflicts, and alternate keyboard layouts on additional Macs before a release.
- Shortcut customization; the current fixed shortcuts report registration conflicts and retain menu-bar fallbacks.
- Signing/notarization, application licensing, and clean-machine distribution.

See [architecture](../../docs/architecture.md) and [the implementation roadmap](../../plan.md).
