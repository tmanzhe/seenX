import type { DemoItem } from "./demo";
import { annotationLimits, isAnnotation, type AnnotationStore } from "./memory-annotations";

export const previewStorageKeys = {
  annotations: "seenx-preview-annotations-v2",
  capture: "seenx-preview-screenshot-v1",
  legacyNotes: "seenx-preview-notes-v1",
} as const;

type StorageReader = Pick<Storage, "getItem">;

function read(storage: StorageReader, key: string): string | null {
  try {
    return storage.getItem(key);
  } catch {
    return null;
  }
}

function parseRecord(raw: string | null): Record<string, unknown> {
  try {
    const value: unknown = JSON.parse(raw ?? "{}");
    return value && typeof value === "object" && !Array.isArray(value)
      ? value as Record<string, unknown>
      : {};
  } catch {
    return {};
  }
}

// Read only known sample IDs. A malformed image's notes must not discard other images.
export function loadPreviewState(storage: StorageReader, items: readonly DemoItem[], captureId: string) {
  const raw = read(storage, previewStorageKeys.annotations);
  const saved = parseRecord(raw);
  const annotations: AnnotationStore = {};

  for (const item of items) {
    const entries = saved[item.id];
    if (Array.isArray(entries) && entries.length <= annotationLimits.perImage && entries.every(isAnnotation)) {
      annotations[item.id] = [...new Map(entries.map((note) => [note.id, note])).values()];
    }
  }

  // An existing v2 store, including an intentionally empty one, takes precedence.
  if (raw === null) {
    const legacy = parseRecord(read(storage, previewStorageKeys.legacyNotes));
    for (const item of items) {
      if (item.id === captureId) continue;
      const text = legacy[item.id];
      if (typeof text === "string" && text.length <= annotationLimits.textLength) {
        annotations[item.id] = text.trim()
          ? [{ id: `migrated-${item.id}`, text, anchor: { type: "image" } }]
          : [];
      }
    }
  }

  return {
    annotations,
    captured: read(storage, previewStorageKeys.capture) === "yes" || Boolean(annotations[captureId]),
  };
}
