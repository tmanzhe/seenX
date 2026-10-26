export const productDescription = "A local visual memory for screenshots, highlights, and your notes. Find saved context yourself or share selected memories with a compatible AI assistant.";

export const roadmapStages = [
  {
    number: "00", title: "Interactive website preview", status: "Available", scope: "Website",
    goal: "Try capture → highlight → note → save → search using authored sample images.",
    tasks: ["Pretend screenshot capture, image results, text selection, point and region notes.", "Browser-local persistence, Command/Ctrl K, and JSON context export."],
    done: "The preview works on desktop and touch devices. It does not access real files, run OCR or vector models, or connect to an assistant.",
  },
  {
    number: "01", title: "Durable local memory + lightweight ontology", status: "Next", scope: "V1",
    goal: "Save a real image and its intention as linked, versioned evidence.",
    tasks: ["SQLite catalog, schema migrations, asset revisions, notes, OCR observations, and normalized point/region targets.", "Typed relationships: note refers to region; region belongs to image revision; image belongs to collection; capture came from a source.", "Keep user assertions, imported facts, and inferred suggestions distinguishable. Add save, edit, export, and removal behavior."],
    done: "Import a real screenshot, attach a note to a region, restart, and recover the same original, selected text, note, and coordinates. Existing Python SQLite is a cache, not this catalog.",
  },
  {
    number: "02", title: "Real OCR + hybrid vector retrieval", status: "Planned", scope: "V1",
    goal: "Find memories by exact words, visual descriptions, and the meaning of your notes.",
    tasks: ["Extend Apple Vision OCR from plain strings to text observations and bounding boxes; normalize orientation and coordinates.", "Use SQLite FTS5 for exact text retrieval. Combine visual vectors and separately evaluated note/text vectors through ranked-result fusion.", "Keep the current local CLIP prototype as a baseline. Evaluate sqlite-vec against exact vector scanning before selecting the shipping index.", "Record model revisions, update edited notes, handle changed sources, and evaluate queries with known matches and genuine no-match cases."],
    done: "A labeled local dataset demonstrates exact, visual, and note-based retrieval with source evidence, repeatable quality measurements, offline runs, and recorded resource costs.",
  },
  {
    number: "03", title: "One engine contract for people and assistants", status: "Planned", scope: "V1",
    goal: "Expose the same stored memories and search behavior to every interface.",
    tasks: ["Define import, annotate, search, fetch memory, fetch region, export, and remove operations.", "Prototype a bounded local Python service over the existing engine; keep it separate from the public website.", "Add background indexing, cancellation, error handling, collection access checks, and versioned result schemas."],
    done: "A local client can save and retrieve the same evidence through a stable contract. APIs return explicit provenance and never treat a screenshot or note as an instruction to execute.",
  },
  {
    number: "04", title: "Native command bar + capture HUD", status: "Planned", scope: "V1 · parallel with MCP",
    goal: "Make saving context and finding it again a small, natural Mac interaction.",
    tasks: ["SwiftUI/AppKit for the search panel, annotation editor, global shortcut, and small optional capture HUD.", "ScreenCaptureKit capture plus selected-source watching. Imported originals stay put; annotations attach to an immutable image revision.", "Capture active-app and URL metadata only through supported integrations and explicit permissions. Unknown source details remain unknown."],
    done: "Take a real screenshot, highlight words or a region, save a thought, press the search shortcut, and find it again after restart. Test display scaling, permission denial, and source changes.",
  },
  {
    number: "05", title: "Read-only MCP bridge + agent evaluation harness", status: "Planned", scope: "V1 · parallel with native UI",
    goal: "Let a compatible assistant retrieve the right memory, highlight, and human intention.",
    tasks: ["Start bridge work alongside native integration once the memory and engine contracts exist.", "Expose bounded search and explicit memory/region fetch over authorized collections. Start with a local stdio client and verify its setup.", "An evaluation harness tests search → select → fetch, source grounding, coordinate accuracy, no-match behavior, and access denial.", "The external client runs the agent. SeenX supplies read-only evidence, not an autonomous agent runtime or arbitrary filesystem access."],
    done: "A tested client retrieves the same image, selected text, coordinates, and notes as human search; revoked sources are unavailable to future requests. Cloud disclosure is explicit.",
  },
  {
    number: "06", title: "Portable library + restore", status: "Planned", scope: "V1 durability",
    goal: "Take your images and their meaning to your next laptop, without starting over.",
    tasks: ["Export all or selected collections as a complete library with image originals, or as context-only metadata that can be relinked to existing files.", "Preserve stable image/revision IDs, notes, selected text, highlights, typed relationships, source history, and a versioned manifest with content hashes.", "Offer an optional passphrase-protected archive. Make a consistent snapshot; keep credentials, assistant grants, and machine-specific permissions out of the transferable library.", "Validate imports, preview missing files and conflicts, and reuse only compatible search indexes. Rebuild derived indexes when needed; reconnect external folders and assistants deliberately."],
    done: "Restore a complete archive into a fresh library on another Mac and recover the same images, notes, highlight coordinates, and relationships. A context-only import identifies and relinks matching originals. Test missing/corrupt files, schema versions, duplicate IDs, and encrypted-archive recovery.",
  },
  {
    number: "07", title: "Production engine + desktop beta", status: "Planned", scope: "V1 release gate",
    goal: "Package a reliable, inspectable local app rather than a collection of demos.",
    tasks: ["Integrate proven catalog and retrieval behavior into the Swift app behind the shared contract. Python remains the evaluation reference.", "Choose local model runtimes after packaging and preprocessing checks; a Core ML integration is not already implemented.", "Validate offline operation after model installation, indexing recovery, note/search updates, deletion, exports, access revocation, and resource use.", "Complete signing, notarization, installation checks, licensing, and the first supported assistant setup."],
    done: "A clean Mac install completes real capture → annotate → restart → human search → assistant retrieval, plus verified export and restore on a second Mac. Production does not require users to install Python.",
  },
] as const;

export const stackChoices = [
  ["Website", "Next.js + React + TypeScript", "Working static preview on Vercel; separate from personal files."],
  ["Prototype engine", "Python", "OCR, CLIP, hybrid rank fusion, and extraction caching exist; durable memory and service APIs are next."],
  ["Persistent memory", "SQLite + FTS5", "Planned catalog, exact text index, notes, source versions, permissions, and typed relationships."],
  ["Semantic retrieval", "Local image/text vectors", "Existing CLIP baseline; note embeddings and sqlite-vec evaluation are planned. Unrelated embedding spaces stay separate."],
  ["Native interface", "SwiftUI + AppKit + ScreenCaptureKit + Vision", "Planned capture, command bar, source permissions, OCR boxes, and annotation UI."],
  ["Assistant access", "MCP", "Read-only V1 plan using the shared engine; no native bridge runs on this website."],
] as const;
