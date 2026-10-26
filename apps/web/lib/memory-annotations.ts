import type { DemoItem } from "./demo";

export type NoteAnchor = { type: "image" } | { type: "point"; x: number; y: number } | { type: "region"; x: number; y: number; width: number; height: number };
export type MemoryAnnotation = { id: string; text: string; quote?: string; anchor: NoteAnchor };
export type AnnotationStore = Record<string, MemoryAnnotation[]>;

export const annotationLimits = {
  perImage: 50,
  idLength: 100,
  textLength: 2000,
  quoteLength: 4000,
} as const;

export const clamp = (value: number) => Math.min(1, Math.max(0, value));

export function regionBetween(start: { x: number; y: number }, end: { x: number; y: number }): NoteAnchor {
  return { type: "region", x: Math.min(start.x, end.x), y: Math.min(start.y, end.y), width: Math.abs(end.x - start.x), height: Math.abs(end.y - start.y) };
}

export function centeredRegion(x = .5, y = .5): NoteAnchor {
  return { type: "region", x: Math.min(.76, Math.max(0, x - .12)), y: Math.min(.82, Math.max(0, y - .09)), width: .24, height: .18 };
}

export function seedAnnotations(item: DemoItem): MemoryAnnotation[] {
  if (!item.note) return [];
  return [{ id: `seed-${item.id}`, text: item.note, anchor: item.id === "layout" ? { type: "region", x: .055, y: .79, width: .89, height: .17 } : { type: "image" } }];
}

export function isAnnotation(value: unknown): value is MemoryAnnotation {
  if (!value || typeof value !== "object") return false;
  const note = value as MemoryAnnotation;
  if (typeof note.id !== "string" || !note.id || note.id.length > annotationLimits.idLength || typeof note.text !== "string" || note.text.length > annotationLimits.textLength || (note.quote !== undefined && (typeof note.quote !== "string" || note.quote.length > annotationLimits.quoteLength)) || (!note.text.trim() && !note.quote?.trim()) || !note.anchor || typeof note.anchor !== "object") return false;
  const anchor = note.anchor;
  if (anchor.type === "image") return true;
  if (anchor.type !== "point" && anchor.type !== "region") return false;
  if (![anchor.x, anchor.y].every((n) => typeof n === "number" && Number.isFinite(n) && n >= 0 && n <= 1)) return false;
  if (anchor.type === "point") return true;
  return [anchor.width, anchor.height].every((n) => typeof n === "number" && Number.isFinite(n) && n > 0 && n <= 1) && anchor.x + anchor.width <= 1.000001 && anchor.y + anchor.height <= 1.000001;
}

export function assistantContext(item: DemoItem, annotations: MemoryAnnotation[], origin: string) {
  return {
    schemaVersion: 1,
    provenance: "authored-website-sample",
    image: { id: item.id, filename: item.file, width: item.width, height: item.height, source: item.source, url: item.image ? new URL(item.image, origin).href : null },
    coordinateSystem: { origin: "top-left", units: "normalized-0-to-1", reference: "full-image", xDirection: "right", yDirection: "down" },
    extractedText: { text: item.text, scope: "whole-image", provenance: "authored-sample" },
    notes: annotations.map((note) => {
      const target = note.anchor;
      const pixels = target.type === "image" ? undefined : target.type === "point"
        ? { x: Math.min(item.width - 1, Math.round(target.x * item.width)), y: Math.min(item.height - 1, Math.round(target.y * item.height)) }
        : { x: Math.floor(target.x * item.width), y: Math.floor(target.y * item.height), width: Math.min(item.width, Math.ceil((target.x + target.width) * item.width)) - Math.floor(target.x * item.width), height: Math.min(item.height, Math.ceil((target.y + target.height) * item.height)) - Math.floor(target.y * item.height) };
      return { id: note.id, text: note.text, ...(note.quote ? { selectedText: { text: note.quote, provenance: "authored-sample-text", scope: "annotated-region" } } : {}), target, ...(pixels ? { pixelBounds: pixels } : {}) };
    }),
    disclosure: "These are sample memories. No assistant is connected. Highlights use authored text boxes for this demo; no OCR or model runs in the browser.",
  };
}

export type SampleTextRegion = { text: string; x: number; y: number; width: number; height: number };
export function sampleTextRegions(item: DemoItem): SampleTextRegion[] {
  if (item.id === "layout" || item.id === "capture-layout") return [
    { text: "form & field", x: .05, y: .035, width: .26, height: .075 },
    { text: "Your everyday essentials.", x: .05, y: .28, width: .5, height: .22 },
    { text: "Thoughtfully made. Made to stay.", x: .05, y: .54, width: .31, height: .09 },
    { text: "Everyday tote", x: .05, y: .815, width: .24, height: .04 },
    { text: "$38.00", x: .85, y: .815, width: .1, height: .04 },
    { text: "Continue to checkout", x: .32, y: .886, width: .36, height: .057 },
  ];
  if (item.id === "terminal") return [
    { text: "$ npm run dev", x: .04, y: .16, width: .35, height: .065 },
    { text: "Error: connection refused", x: .04, y: .345, width: .58, height: .06 },
    { text: "ECONNREFUSED 127.0.0.1:5432", x: .04, y: .435, width: .65, height: .05 },
  ];
  if (item.id === "menu") return [
    { text: "GOOD THINGS, SLOWLY.", x: .06, y: .2, width: .8, height: .27 },
    { text: "Matcha latte ¥550", x: .07, y: .67, width: .86, height: .07 },
    { text: "Pour-over coffee ¥480", x: .07, y: .79, width: .86, height: .07 },
  ];
  return [];
}

export function textAtAnchor(item: DemoItem, anchor: NoteAnchor) {
  if (anchor.type === "image") return "";
  return sampleTextRegions(item).filter((box) => {
    if (anchor.type === "point") return anchor.x >= box.x && anchor.x <= box.x + box.width && anchor.y >= box.y && anchor.y <= box.y + box.height;
    const width = Math.max(0, Math.min(anchor.x + anchor.width, box.x + box.width) - Math.max(anchor.x, box.x));
    const height = Math.max(0, Math.min(anchor.y + anchor.height, box.y + box.height) - Math.max(anchor.y, box.y));
    return width * height / (box.width * box.height) >= .35;
  }).map((box) => box.text).join("\n");
}
