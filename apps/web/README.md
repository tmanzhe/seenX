# seenX web

A Next.js App Router website for a local visual memory: saved images, the thoughts attached to them, and optional assistant retrieval.

## Current behavior

- Responsive sky-blue glass styling, with a dark theme and reduced-motion support.
- Spacious opening with the headline and two actions, with the demo bar peeking above the fold, followed by a scroll-driven Capture / Annotate / Recall walkthrough. Native scrolling, reversible stages, and a compact static guide for reduced motion.
- Scroll-drawn orbital trails and a layered ASCII contour field with shaded 3D logo cubes; decorative motion pauses offscreen and respects reduced motion.
- Capture/save acknowledgements, responsive hover feedback, and small motion effects that respect reduced-motion preferences.
- A normal search bar with image results, plus a pretend screenshot → highlight → save → Command/Ctrl K search flow.
- Whole-image notes, click-to-pin notes, drawn area annotations, and selectable authored text boxes. Saved highlights and notes are searchable.
- A memory detail view with separate user notes, authored sample extracted text, and illustrative source labels.
- Copy for assistant and JSON export include saved notes, selected text, full-image dimensions, normalized coordinates, and pixel bounds. Unsaved drafts must be saved or canceled before export.
- Documentation for the native command bar, capture HUD, local retrieval, source metadata, V1 MCP, and portable-library backup/restore. Transfer and optional encrypted archives are planned; single-memory JSON export is the current preview capability.
- The existing learning journal and its separate personal-notes notebook.
- Static export; no real file access, upload endpoint, account service, semantic inference, or assistant connection.

Sample search uses accent-insensitive keyword matches over authored records, with additional weight for user notes. Annotations use `seenx-preview-annotations-v2`; the simulated capture uses `seenx-preview-screenshot-v1`. Older `seenx-preview-notes-v1` edits migrate as whole-image notes. Clearing browser storage removes sample edits and captures. The separate learning notebook is not part of sample-memory search.

Native app capture, a system-wide hotkey, app/URL metadata collection, and MCP integration are planned capabilities. Website copy must distinguish these from working preview behavior. Source context is recorded only where an actual integration and permissions support it.

## Development

From the repository root:

```sh
npm ci
npm run dev
npm run typecheck
npm run build
```

Use `npm run dev -- --port 3015` to select another local port. The production export is written to `out/` in this directory.

Documentation content lives in `lib/docs.tsx`, navigation in `lib/docs-navigation.ts`, and sample memories in `lib/demo.ts`. The shared layout and stylesheet live under `app/`. There is no additional UI framework or remote font dependency.

## Sample imagery

Bundled, compressed photographs originate from Unsplash:

- [Alpine lake](https://images.unsplash.com/photo-1470770841072-f978cf4d019e)
- [Mountain light](https://images.unsplash.com/photo-1469474968028-56623f02e42e)
- [Coastline](https://images.unsplash.com/photo-1518837695005-2083093ee35b)
- [Mountain peak](https://images.unsplash.com/photo-1464822759023-fed622ff2c3b)

The checkout, terminal, and café menu are authored SVG illustrations with fixed viewBoxes so spatial annotations stay aligned across screen sizes. The Text tool uses authored text boxes, not live OCR. Sample notes, OCR text, and source details are illustrative; they were not extracted from these assets. Review the applicable [Unsplash terms](https://unsplash.com/license) before redistributing photographs beyond this demo.

## Deployment

The static website is hosted in the `seenx` Vercel project at <https://seenx-lovat.vercel.app>. A website deployment does not provide a native app, a hosted memory database, or an MCP endpoint. The current release direction remains free/open source with optional support; no payment or donation flow is configured.
