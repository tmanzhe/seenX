import assert from "node:assert/strict";
import test from "node:test";
import { demoItems } from "../lib/demo";
import { annotationLimits, assistantContext, isAnnotation, regionBetween, textAtAnchor, type MemoryAnnotation } from "../lib/memory-annotations";

const note: MemoryAnnotation = { id: "note-1", text: "Keep this", anchor: { type: "image" } };

test("annotation validation accepts quote-only highlights and inclusive image edges", () => {
  assert.equal(isAnnotation({ ...note, text: "", quote: "Checkout" }), true);
  assert.equal(isAnnotation({ ...note, anchor: { type: "point", x: 1, y: 0 } }), true);
  assert.equal(isAnnotation({ ...note, anchor: { type: "region", x: 0, y: 0, width: 1, height: 1 } }), true);
});

test("annotation validation rejects malformed notes and nonfinite or out-of-bounds geometry", () => {
  for (const value of [null, [], {}, { ...note, text: " " }, { ...note, quote: 42 },
    { ...note, anchor: { type: "point", x: NaN, y: 0 } },
    { ...note, anchor: { type: "point", x: 0, y: Infinity } },
    { ...note, anchor: { type: "point", x: -.1, y: 0 } },
    { ...note, anchor: { type: "region", x: .9, y: 0, width: .2, height: .1 } },
    { ...note, anchor: { type: "region", x: 0, y: 0, width: 0, height: .1 } },
  ]) assert.equal(isAnnotation(value), false);
});

test("annotation limits accept boundary lengths and reject larger payloads", () => {
  for (const [field, limit] of [["id", annotationLimits.idLength], ["text", annotationLimits.textLength], ["quote", annotationLimits.quoteLength]] as const) {
    assert.equal(isAnnotation({ ...note, [field]: "x".repeat(limit) }), true);
    assert.equal(isAnnotation({ ...note, [field]: "x".repeat(limit + 1) }), false);
  }
});

test("exported pins at the image edge stay inside the final pixel", () => {
  const item = demoItems[0];
  const context = assistantContext(item, [{ ...note, anchor: { type: "point", x: 1, y: 1 } }], "https://example.com");
  assert.deepEqual(context.notes[0].pixelBounds, { x: item.width - 1, y: item.height - 1 });
});

test("export preserves image identity, quoted text, and a full-image region's pixel bounds", () => {
  const item = demoItems[0];
  const context = assistantContext(item, [{ ...note, quote: "Checkout", anchor: { type: "region", x: 0, y: 0, width: 1, height: 1 } }], "https://example.com");
  assert.equal(context.image.id, item.id);
  assert.deepEqual(context.notes[0].pixelBounds, { x: 0, y: 0, width: item.width, height: item.height });
  assert.equal(context.notes[0].selectedText?.text, "Checkout");
});

test("reverse-direction selection preserves text and normalized bounds", () => {
  const anchor = regionBetween({ x: 1, y: 1 }, { x: 0, y: .8 });
  assert.equal(anchor.type, "region");
  assert.match(textAtAnchor(demoItems[0], anchor), /Continue to checkout/);
});
