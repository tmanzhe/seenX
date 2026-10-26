import assert from "node:assert/strict";
import test from "node:test";
import { demoItems, searchDemo } from "../lib/demo";
import { annotationLimits, type MemoryAnnotation } from "../lib/memory-annotations";
import { loadPreviewState, previewStorageKeys } from "../lib/preview-storage";

const capture = { ...demoItems[0], id: "capture-layout", note: "" };
const items = [...demoItems, capture];
const note: MemoryAnnotation = { id: "note-1", text: "Softer colors", anchor: { type: "point", x: .5, y: .25 } };

function load(values: Record<string, string> = {}) {
  return loadPreviewState({ getItem: (key) => values[key] ?? null }, items, capture.id);
}

test("empty or inaccessible storage leaves the sample usable", () => {
  const empty = { annotations: {}, captured: false };
  assert.deepEqual(load(), empty);
  assert.deepEqual(loadPreviewState({ getItem() { throw new Error("Access denied"); } }, items, capture.id), empty);
});

test("valid notes round trip and remain searchable", () => {
  const state = load({ [previewStorageKeys.annotations]: JSON.stringify({ layout: [note] }) });
  assert.deepEqual(state.annotations.layout, [note]);
  const notes = { layout: state.annotations.layout.map((entry) => entry.text).join(" ") };
  assert.equal(searchDemo("Softer colors", "all", "all", notes)[0]?.id, "layout");
});

test("unknown sample IDs are ignored", () => {
  const state = load({ [previewStorageKeys.annotations]: JSON.stringify({ unknown: [note], layout: [note] }) });
  assert.deepEqual(Object.keys(state.annotations), ["layout"]);
});

test("a malformed image entry does not discard other saved images", () => {
  const state = load({ [previewStorageKeys.annotations]: JSON.stringify({ layout: [note], lake: [null], menu: "bad" }) });
  assert.deepEqual(state.annotations, { layout: [note] });
});

test("invalid geometry is rejected during restoration", () => {
  const invalid = { ...note, anchor: { type: "region", x: .9, y: .1, width: .2, height: .1 } };
  assert.deepEqual(load({ [previewStorageKeys.annotations]: JSON.stringify({ layout: [invalid] }) }).annotations, {});
});

test("duplicate IDs keep the last saved note", () => {
  const latest = { ...note, text: "Latest revision" };
  assert.deepEqual(load({ [previewStorageKeys.annotations]: JSON.stringify({ layout: [note, latest] }) }).annotations.layout, [latest]);
});

test("the annotation limit accepts the boundary and rejects oversized entries", () => {
  const notes = Array.from({ length: annotationLimits.perImage }, (_, index) => ({ ...note, id: `note-${index}` }));
  assert.equal(load({ [previewStorageKeys.annotations]: JSON.stringify({ layout: notes }) }).annotations.layout.length, annotationLimits.perImage);
  assert.deepEqual(load({ [previewStorageKeys.annotations]: JSON.stringify({ layout: [...notes, { ...note, id: "extra" }] }) }).annotations, {});
});

test("legacy notes migrate as whole-image notes, including intentional deletions", () => {
  const state = load({ [previewStorageKeys.legacyNotes]: JSON.stringify({ layout: "Keep this", lake: "  ", unknown: "Ignore" }) });
  assert.deepEqual(state.annotations, {
    layout: [{ id: "migrated-layout", text: "Keep this", anchor: { type: "image" } }],
    lake: [],
  });
});

test("oversized legacy notes and captures do not migrate", () => {
  const state = load({ [previewStorageKeys.legacyNotes]: JSON.stringify({ layout: "x".repeat(annotationLimits.textLength + 1), [capture.id]: "Old capture" }) });
  assert.deepEqual(state.annotations, {});
  assert.equal(state.captured, false);
});

test("existing v2 data takes precedence over legacy notes, including empty and corrupt stores", () => {
  for (const raw of ["{}", "{", "null", "[]", "42", JSON.stringify({ layout: [] })]) {
    const state = load({
      [previewStorageKeys.annotations]: raw,
      [previewStorageKeys.legacyNotes]: JSON.stringify({ layout: "Do not resurrect" }),
    });
    assert.deepEqual(state.annotations.layout ?? [], []);
  }
});

test("malformed annotation JSON does not hide a saved capture", () => {
  const state = load({ [previewStorageKeys.annotations]: "{", [previewStorageKeys.capture]: "yes" });
  assert.deepEqual(state.annotations, {});
  assert.equal(state.captured, true);
});

test("saved capture notes restore capture visibility even when all notes were removed", () => {
  for (const notes of [[note], []]) {
    const state = load({ [previewStorageKeys.annotations]: JSON.stringify({ [capture.id]: notes }) });
    assert.deepEqual(state.annotations[capture.id], notes);
    assert.equal(state.captured, true);
  }
});

test("loading does not rewrite storage during migration or recovery", () => {
  const values = { [previewStorageKeys.legacyNotes]: JSON.stringify({ layout: "Original note" }) };
  const before = JSON.stringify(values);
  load(values);
  assert.equal(JSON.stringify(values), before);
});
