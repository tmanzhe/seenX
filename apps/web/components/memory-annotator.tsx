"use client";

import { useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import type { DemoItem } from "../lib/demo";
import { assistantContext, centeredRegion, clamp, regionBetween, sampleTextRegions, textAtAnchor, type MemoryAnnotation, type NoteAnchor } from "../lib/memory-annotations";
import { Icon } from "./icon";
import { MemoryArtwork } from "./memory-artwork";

function locationLabel(anchor: NoteAnchor) {
  if (anchor.type === "image") return "Whole image";
  const xy = `${Math.round(anchor.x * 100)}%, ${Math.round(anchor.y * 100)}%`;
  return anchor.type === "point" ? `Pin at ${xy}` : `Area at ${xy} · ${Math.round(anchor.width * 100)}% × ${Math.round(anchor.height * 100)}%`;
}

export function MemoryAnnotator({ item, annotations, onChange, onClose, onSearch }: { item: DemoItem; annotations: MemoryAnnotation[]; onChange: (next: MemoryAnnotation[]) => boolean; onClose: () => void; onSearch: () => void }) {
  const [mode, setMode] = useState<"pin" | "area" | "text">(item.id === "capture-layout" ? "text" : "pin");
  const [anchor, setAnchor] = useState<NoteAnchor | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [quote, setQuote] = useState("");
  const [message, setMessage] = useState("");
  const [drawing, setDrawing] = useState<NoteAnchor | null>(null);
  const surface = useRef<HTMLDivElement>(null);
  const textarea = useRef<HTMLTextAreaElement>(null);
  const drag = useRef<{ x: number; y: number; clientX: number; clientY: number; pointerId: number } | null>(null);
  const current = annotations.find((note) => note.id === editingId);
  const dirty = current ? draft !== current.text || quote !== (current.quote ?? "") || JSON.stringify(anchor) !== JSON.stringify(current.anchor) : Boolean(anchor && (draft.trim() || quote));
  const textBoxes = sampleTextRegions(item);

  function focusEditor() { requestAnimationFrame(() => textarea.current?.focus()); }
  function canSwitch() {
    if (!dirty) return true;
    setMessage("Save or cancel your current note before choosing another spot.");
    focusEditor();
    return false;
  }
  function create(target: NoteAnchor, selectedText = textAtAnchor(item, target)) {
    if (!canSwitch()) return;
    if (annotations.length >= 50) { setMessage("This sample supports up to 50 notes per image."); return; }
    setAnchor(target); setEditingId(null); setDraft(""); setQuote(selectedText); setMessage(""); focusEditor();
  }
  function select(note: MemoryAnnotation) {
    if (note.id === editingId) { focusEditor(); return; }
    if (!canSwitch()) return;
    setEditingId(note.id); setAnchor(note.anchor); setDraft(note.text); setQuote(note.quote ?? ""); setMessage(""); focusEditor();
  }
  function cancel() { setAnchor(null); setEditingId(null); setDraft(""); setQuote(""); setMessage(""); surface.current?.focus(); }
  function save() {
    if (!anchor || (!draft.trim() && !quote)) return;
    const id = editingId ?? crypto.randomUUID();
    const note = { id, text: draft.trim(), ...(quote ? { quote } : {}), anchor };
    const next = editingId ? annotations.map((entry) => entry.id === id ? note : entry) : [...annotations, note];
    const persisted = onChange(next);
    setEditingId(id); setDraft(note.text);
    setMessage(persisted ? "Saved. Press ⌘ K to find this screenshot by your highlight or note." : "Saved for this visit. Browser storage is unavailable.");
  }
  function remove(id: string) {
    onChange(annotations.filter((note) => note.id !== id));
    if (editingId === id) { setAnchor(null); setEditingId(null); setDraft(""); setQuote(""); }
    setMessage("Note removed from this sample memory.");
  }
  function coordinates(event: PointerEvent<HTMLDivElement>) {
    const bounds = event.currentTarget.getBoundingClientRect();
    return { x: clamp((event.clientX - bounds.left) / bounds.width), y: clamp((event.clientY - bounds.top) / bounds.height) };
  }
  function pointerDown(event: PointerEvent<HTMLDivElement>) {
    if (event.button !== 0 || (event.target instanceof Element && event.target.closest("button:not(.annotation-text-hitbox)"))) return;
    if (!canSwitch()) return;
    const point = coordinates(event);
    drag.current = { ...point, clientX: event.clientX, clientY: event.clientY, pointerId: event.pointerId };
    event.currentTarget.setPointerCapture(event.pointerId);
    event.preventDefault();
  }
  function pointerMove(event: PointerEvent<HTMLDivElement>) {
    if (!drag.current || drag.current.pointerId !== event.pointerId) return;
    const distance = Math.hypot(event.clientX - drag.current.clientX, event.clientY - drag.current.clientY);
    if (distance >= 7) setDrawing(regionBetween(drag.current, coordinates(event)));
  }
  function pointerUp(event: PointerEvent<HTMLDivElement>) {
    const start = drag.current;
    if (!start || start.pointerId !== event.pointerId) return;
    const end = coordinates(event);
    const region = regionBetween(start, end);
    const distance = Math.hypot(event.clientX - start.clientX, event.clientY - start.clientY);
    drag.current = null; setDrawing(null);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
    if (mode === "text" && distance < 7) {
      const box = textBoxes.find((box) => end.x >= box.x && end.x <= box.x + box.width && end.y >= box.y && end.y <= box.y + box.height);
      if (box) { create({ type: "region", x: box.x, y: box.y, width: box.width, height: box.height }, box.text); return; }
    }
    create(distance >= 7 && region.type === "region" && region.width > .005 && region.height > .005 ? region : mode === "area" ? centeredRegion(end.x, end.y) : { type: "point", ...end });
  }
  function keyboard(event: KeyboardEvent<HTMLDivElement>) {
    if (event.target !== event.currentTarget) return;
    if (event.key === "Enter" || event.key === " ") { event.preventDefault(); create(mode !== "pin" ? centeredRegion() : { type: "point", x: .5, y: .5 }); }
    if (anchor && anchor.type !== "image" && ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) {
      event.preventDefault();
      const step = event.shiftKey ? .05 : .01;
      const next = { ...anchor, x: Math.min(anchor.type === "region" ? 1 - anchor.width : 1, clamp(anchor.x + (event.key === "ArrowLeft" ? -step : event.key === "ArrowRight" ? step : 0))), y: Math.min(anchor.type === "region" ? 1 - anchor.height : 1, clamp(anchor.y + (event.key === "ArrowUp" ? -step : event.key === "ArrowDown" ? step : 0))) };
      setAnchor(next); setQuote(textAtAnchor(item, next));
    }
  }
  function noteStyle(target: NoteAnchor) {
    return target.type === "image" ? {} : { left: `${target.x * 100}%`, top: `${target.y * 100}%`, ...(target.type === "region" ? { width: `${target.width * 100}%`, height: `${target.height * 100}%` } : {}) };
  }
  function context() { return JSON.stringify(assistantContext(item, annotations, location.origin), null, 2); }
  async function copy() {
    try { await navigator.clipboard.writeText(context()); setMessage("Assistant context copied with saved notes and their coordinates."); }
    catch { setMessage("Clipboard unavailable. Export JSON to download the same context."); }
  }
  function exportContext() {
    const url = URL.createObjectURL(new Blob([context()], { type: "application/json" }));
    const link = document.createElement("a"); link.href = url; link.download = `seenx-${item.id}-context.json`; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    setMessage("Context exported with saved notes, image dimensions, and coordinates.");
  }

  return <>
    <div className="annotation-header"><div><span className="eyebrow">A LITTLE CONTEXT, RIGHT WHERE IT BELONGS</span><h2 id="preview-title">{item.title}</h2></div><button className="annotation-back-search text-link" onClick={onSearch}>Back to search <kbd>⌘ K</kbd></button><button className="dialog-close icon-button" aria-label="Close image preview" onClick={onClose}><Icon name="close" /></button></div>
    <div className="annotation-layout"><div className="annotation-canvas-column"><div className="annotation-toolbar"><div role="group" aria-label="Annotation tool"><button aria-pressed={mode === "pin"} onClick={() => setMode("pin")}><Icon name="pin" size={14} /> Pin</button><button aria-pressed={mode === "area"} onClick={() => setMode("area")}><Icon name="region" size={14} /> Highlight</button>{textBoxes.length > 0 && <button aria-pressed={mode === "text"} onClick={() => setMode("text")}><Icon name="code" size={14} /> Text</button>}</div><span>{mode === "text" ? "Click a text highlight, or drag over words." : "Click a spot. Drag over an area."}</span></div>
      <div ref={surface} className="annotation-surface" tabIndex={0} role="group" aria-label="Annotate image: click to pin a note, or drag to highlight an area" aria-describedby="annotation-keyboard-help" style={{ aspectRatio: `${item.width} / ${item.height}` }} onPointerDown={pointerDown} onPointerMove={pointerMove} onPointerUp={pointerUp} onPointerCancel={() => { drag.current = null; setDrawing(null); }} onLostPointerCapture={() => { drag.current = null; setDrawing(null); }} onKeyDown={keyboard}>
        <MemoryArtwork item={item} />
        {mode === "text" && textBoxes.map((box, index) => <button key={index} className="annotation-text-hitbox" aria-label={`Highlight text: ${box.text}`} style={{left:`${box.x * 100}%`,top:`${box.y * 100}%`,width:`${box.width * 100}%`,height:`${box.height * 100}%`}} onClick={(event) => { if(event.detail === 0) create({type:"region",x:box.x,y:box.y,width:box.width,height:box.height}, box.text); }}><span className="sr-only">{box.text}</span></button>)}
        {annotations.map((note, index) => note.anchor.type !== "image" && <div key={note.id} className={`annotation-mark annotation-${note.anchor.type} ${editingId === note.id ? "is-selected" : ""}`} style={noteStyle(editingId === note.id && anchor ? anchor : note.anchor)}><button data-annotation-marker aria-label={`Select note ${index + 1}: ${note.text || note.quote}`} aria-pressed={editingId === note.id} onClick={(event) => { event.stopPropagation(); select(note); }}>{index + 1}</button></div>)}
        {anchor && !editingId && anchor.type !== "image" && <div className={`annotation-mark annotation-${anchor.type} annotation-draft`} style={noteStyle(anchor)}><span>+</span></div>}
        {drawing?.type === "region" && <div className="annotation-mark annotation-region annotation-drawing" style={noteStyle(drawing)} />}
      </div>
      <p className="annotation-help" id="annotation-keyboard-help">Keyboard: focus the image and press Enter to place a {mode === "area" ? "highlight" : "pin"} in the center. Arrow keys move the selected location; Shift moves it farther.</p>
      <div className="memory-source"><Icon name="image" size={14} /><span>{item.file}<small>{item.source} · illustrative source</small></span><span className="annotation-size">{item.width} × {item.height}</span></div>
    </div><aside className="annotation-sidebar" aria-label="Image notes"><div className="annotation-sidebar-heading"><h3>Your notes <span>{annotations.length}</span></h3><button className="text-link" onClick={() => create({ type: "image" })}>Add image note <Icon name="plus" size={13} /></button></div>
      <div className="annotation-note-list">{annotations.map((note, index) => <div className={`annotation-note ${editingId === note.id ? "is-selected" : ""}`} key={note.id}><button className="annotation-note-select" onClick={() => select(note)} aria-label={`Edit note ${index + 1}`}><span className="annotation-note-number">{index + 1}</span><span><small>{note.anchor.type === "image" ? "Whole image" : note.anchor.type === "point" ? "Pinned to a spot" : "Highlighted area"}</small>{note.quote && <q className="annotation-quote-preview">{note.quote}</q>}{note.text && <span>{note.text}</span>}</span></button><button className="annotation-delete" aria-label={`Delete note ${index + 1}`} onClick={() => remove(note.id)}><Icon name="close" size={12} /></button></div>)}</div>
      {anchor ? <form className="annotation-composer" onSubmit={(event) => { event.preventDefault(); save(); }}><label htmlFor="memory-note">{editingId ? "Edit your note" : "What about this part?"}<span>{locationLabel(anchor)}</span></label>{quote && <blockquote className="annotation-selected-text"><span>Selected text</span>{quote}</blockquote>}<textarea ref={textarea} id="memory-note" value={draft} onChange={(event) => { setDraft(event.target.value); setMessage(""); }} placeholder={quote ? "Add a thought about this text (optional)…" : anchor.type === "image" ? "What made this image worth saving?" : "What should someone know about this exact spot?"} maxLength={2000} rows={4} /><div className="annotation-composer-actions"><button className="text-link" type="button" onClick={cancel}>Cancel</button><button className="button button-dark button-small" type="submit" disabled={(!draft.trim() && !quote) || !dirty}>{quote ? "Save highlight" : "Save note"} <Icon name="check" size={13} /></button></div></form> : <div className="annotation-empty"><Icon name="pin" size={22} /><strong>Point to what you mean.</strong><p>Pin a thought to a detail, or highlight an area. Your assistant gets the note and its exact location.</p></div>}
      {editingId && !dirty && <button className="annotation-find-saved" onClick={onSearch}>Find it in your memories <kbd>⌘ K</kbd><Icon name="arrow" size={14} /></button>}
      <p className="annotation-feedback" role="status" aria-live="polite">{message || (dirty ? "Save your note to include it in search and assistant context." : "Notes are saved in this browser and included in sample search.")}</p>
      <details className="memory-text"><summary>Text in this sample <Icon name="code" size={13} /></summary><p>{item.text}</p><small>Full-image text. The Text tool uses authored text boxes in this preview.</small></details>
      <div className="memory-share"><button className="text-link" onClick={copy} disabled={dirty}>Copy for assistant <Icon name="arrow" size={14} /></button><button className="text-link" onClick={exportContext} disabled={dirty}>Export JSON <Icon name="diagonal" size={14} /></button></div><p className="memory-demo-disclaimer">Sample images only. This preview saves your notes and their locations; it does not connect to an assistant.</p>
    </aside></div>
  </>;
}
