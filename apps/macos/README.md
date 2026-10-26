# seenX macOS app

A basic native menu-bar app: a translucent search panel, quick screenshots, and screenshots with text highlights and a note. Built with SwiftUI/AppKit and Apple Vision on macOS 14 or later. This slice uses Apple frameworks without a Python runtime or third-party packages. Shared retrieval integration remains planned.

The interface follows the seenX Design Proposal with a launcher flow: compact glass search, a thumbnail library and saved-image previews inside the same floating panel, an image-led annotation stage with an inline note, and a first-run permission screen. The default is clear white Liquid Glass with a subtle blue tint, independent of the system appearance. macOS 26+ uses native clear Liquid Glass; macOS 14–25 use a frosted fallback. Reduce Transparency uses opaque surfaces.

## Build and open

With Xcode installed, from the repository root:

```sh
bash apps/macos/build.sh
open apps/macos/.build/app/seenX.app
```

The script creates an ad-hoc signed local development app. It prefers the existing full Xcode installation unless you set `DEVELOPER_DIR`; it does not change the system developer-tool selection. This is not a notarized release or a distributable download.

Ad-hoc signatures can change when the app is rebuilt. macOS can then show an enabled Screen Recording entry while the running copy still lacks access. Quit the previous process and reopen the current app after a rebuild. For stable development authorization, set `SEENX_CODE_SIGN_IDENTITY` to an installed Apple Development/Developer ID signing identity when building; ad-hoc signing remains the fallback when none is supplied.

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

The `seenX` menu-bar item provides the same actions, Open Library, Try a sample image, and Quit. An empty launcher offers capture and library commands; use arrows and Enter to run them. Opening a search result or the library navigates within the same panel, with a back button and preserved search context. The compact Actions menu holds secondary commands and the glass-background opacity control. Screen selection uses macOS's own screenshot tool. macOS may ask for Screen & System Audio Recording permission; no audio recording is used. Canceling the system selector does not create a memory.

The app has no Dock icon. To quit without finding its menu-bar item, summon it with **⌘⇧K** and press **⌘Q**, or use **Actions → Quit seenX**. **Actions → Restart seenX** safely relaunches the current app bundle. Hiding the overlay keeps the app running.

## First run

The welcome panel explains screen access before asking macOS for permission. Choose **Allow screen access**, **Try a sample image instead**, or the close button to set up later. The sample is an authored invoice image; it does not access the screen, and enters the library only if you explicitly save it. A denied screen permission can be enabled in System Settings. The recovery screen provides **Try again** (checks the actual capture API) and **Restart seenX** (protects any unsaved draft before relaunching). Returning from Settings automatically retries when the system reports a new grant. Search, the library, and sample annotations work without screen access.

If Screen Recording is already enabled but access is still denied after reopening, remove the old seenX entry in System Settings and add this current app bundle again. The app never resets macOS privacy settings or grants itself access. Permission checks use ScreenCaptureKit metadata; screenshot pixels are read only after you choose a capture action and complete the system region selector. Capture failures now show their error instead of being silently treated as cancellation.

## Highlight and save

1. Capture with **⌘⇧−**.
2. Wait for on-device text recognition. Click a recognized text box or drag across boxes to select text. Selection initially remains pending.
3. Press **⌘Enter** to commit that highlight. Repeat to add more highlights, and optionally write in the floating **Add a thought…** field beside the selection.
4. Press **⌘Enter** with no pending selection to save and close. With no highlights selected, a note-only capture saves on the first press.

Highlights refer to recognized text boxes, not arbitrary painted regions or character-level text ranges. Their coordinates use a normalized top-left origin, so they follow the screenshot when the preview resizes. OCR can miss text; a capture still saves without recognized text. Save failures keep the draft open.

Search matches words in recognized text, notes, and highlights. An empty query lists recent captures. This is local literal search, not semantic/visual retrieval. Open a saved result to inspect the original image and saved context.

## Storage and boundaries

Screenshots and an atomically written `library.json` manifest live in `~/Library/Application Support/seenX Native/`. Restarting the app reloads this library. These files are separate from the Python catalog and the website's sample data. There is no cloud upload, assistant connection, or automatic access to other folders in this slice.

The app captures only after a deliberate capture action. Its panels are hidden during capture. A new capture does not replace an unfinished annotation draft. The opacity slider adjusts only the glass background; text and controls retain full contrast. The annotation image stays opaque so highlights remain readable. Search remembers its position between shortcut toggles. Movement shortcuts are registered only while the launcher is visible, so other apps regain their usual text-selection shortcuts when it is hidden.

## Remaining integration

- Connect the native UI to a shared catalog and measured retrieval engine; reconcile the development library through an explicit import/migration rather than silently opening the Python database.
- Character-level text selection, editable saved annotations, image import, and library deletion/organization.
- ScreenCaptureKit capture adapter, supported source metadata, source permission management, portable backup/restore, and an opt-in read-only MCP bridge.
- Verify Retina/multi-display selection, permission denial/revocation, shortcut conflicts, and alternate keyboard layouts on additional Macs before a release.
- Shortcut customization; the current fixed shortcuts report registration conflicts and retain menu-bar fallbacks.
- Signing/notarization, application licensing, and clean-machine distribution.

See [architecture](../../docs/architecture.md) and [the implementation roadmap](../../plan.md).
