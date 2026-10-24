# seenX web

A Next.js App Router site for explaining seenX, documenting the architecture, and demonstrating its intended search interaction.

## Current behavior

- A responsive product page with a searchable, filterable sample library and image previews.
- A documentation hub with grouped navigation, local search, article outlines, and previous/next links.
- Use cases for personal search and AI agents, alongside architecture, privacy, and roadmap.
- Python-to-Rust learning and ontology guides; the homepage compares retrieval workflows and describes planned evaluation metrics.
- Learning notes and the browser notebook at `/docs/learning`; the previous `/learning` address remains an alias with the same browser storage.
- A support page explaining the free/open-source direction without a payment flow.
- Static export; no image-upload endpoint, account service, or AI API.

The sample search performs keyword matches over authored records. The collection labels are illustrative, not GPS data extracted from the photographs. Desktop functionality and agent integration remain planned.

## Development

From the repository root:

```sh
npm ci
npm run dev
npm run typecheck
npm run build
```

To select another local port, use `npm run dev -- --port 3015`. The production export is written to this directory's `out/` folder and can be served by a static host.

Content for the documentation lives in `lib/docs.tsx`, with navigation groups in `lib/docs-navigation.ts`. Documentation search includes public article text and shared learning concepts; personal browser notes are not indexed. Sample records live in `lib/demo.ts`. The shared layout and stylesheet live under `app/`. No additional UI framework or remote font download is needed.

## Sample imagery

Bundled, compressed photographs originate from Unsplash:

- [Alpine lake](https://images.unsplash.com/photo-1470770841072-f978cf4d019e)
- [Mountain light](https://images.unsplash.com/photo-1469474968028-56623f02e42e)
- [Coastline](https://images.unsplash.com/photo-1518837695005-2083093ee35b)
- [Mountain peak](https://images.unsplash.com/photo-1464822759023-fed622ff2c3b)

The terminal and café menu are authored HTML/CSS illustrations. Sample image files are served locally with the site. Photographs are not covered by the future code license; retain their source information and review the applicable [Unsplash terms](https://unsplash.com/license) before redistributing assets beyond this demo.

## Publication

The site remains local. No public repository, donation link, license, application download, or deployment has been configured. Product copy must continue to distinguish implemented behavior from proposed features.
