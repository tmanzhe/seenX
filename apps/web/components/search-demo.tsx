"use client";

import { useEffect, useRef, useState } from "react";
import { demoItems, searchDemo, type DemoItem } from "../lib/demo";
import { seedAnnotations, type AnnotationStore, type MemoryAnnotation } from "../lib/memory-annotations";
import { loadPreviewState, previewStorageKeys } from "../lib/preview-storage";
import { Icon } from "./icon";
import { MemoryArtwork } from "./memory-artwork";
import { MemoryAnnotator } from "./memory-annotator";

const captureItem: DemoItem = { ...demoItems[0], id: "capture-layout", title: "Your checkout screenshot", file: "your-checkout-capture.png", location: "Your captures", source: "Pretend screenshot · example.com/shop", note: "" };
const availableItems = [...demoItems, captureItem];

export function SearchDemo() {
  const [query, setQuery] = useState("");
  const [store, setStore] = useState<AnnotationStore>({});
  const [selected, setSelected] = useState<DemoItem | null>(null);
  const [ready, setReady] = useState(false);
  const [captured, setCaptured] = useState(false);
  const [capturePreview, setCapturePreview] = useState(false);
  const [toast, setToast] = useState<{ id: number; title: string; detail: string } | null>(null);
  const toastId = useRef(0);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const notesFor = (item: DemoItem) => store[item.id] ?? seedAnnotations(item);
  const searchableNotes = Object.fromEntries(availableItems.map((item) => [item.id, notesFor(item).map((note) => `${note.text} ${note.quote ?? ""}`).join(" ")]));
  const results = searchDemo(query, "all", "all", searchableNotes, captured ? availableItems : demoItems);

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 3400);
    return () => clearTimeout(timer);
  }, [toast]);

  useEffect(() => {
    try {
      const restored = loadPreviewState(localStorage, availableItems, captureItem.id);
      setStore(restored.annotations);
      setCaptured(restored.captured);
    } catch { /* A fresh sample still works when browser storage is unavailable. */ }
    setReady(true);
    const shortcut = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") { event.preventDefault(); returnToSearch(); }
    };
    window.addEventListener("keydown", shortcut);
    return () => window.removeEventListener("keydown", shortcut);
  }, []);

  useEffect(() => { if ((selected || capturePreview) && !dialogRef.current?.open) dialogRef.current?.showModal(); }, [selected, capturePreview]);

  function returnToSearch() {
    dialogRef.current?.close(); setSelected(null); setCapturePreview(false); setQuery("");
    requestAnimationFrame(() => { searchRef.current?.focus(); searchRef.current?.scrollIntoView({ block: "center", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth" }); });
  }

  function notify(title: string, detail: string) { setToast({ id: ++toastId.current, title, detail }); }

  function captureScreenshot() {
    notify("Screenshot captured", "Now give the detail a little context.");
    setCaptured(true); setCapturePreview(false); setSelected(captureItem);
    try { localStorage.setItem(previewStorageKeys.capture, "yes"); } catch { /* Keep the sample capture for this visit. */ }
  }

  function saveAnnotations(next: MemoryAnnotation[]) {
    if (!selected) return false;
    const updated = { ...store, [selected.id]: next };
    setStore(updated);
    try {
      localStorage.setItem(previewStorageKeys.annotations, JSON.stringify(updated));
      const previousCount = notesFor(selected).length;
      notify(next.length < previousCount ? "Note removed" : next.length > previousCount ? "Context saved" : "Memory updated", "Your words and their location stay together.");
      return true;
    }
    catch { return false; }
  }

  const toastView = toast && <div key={toast.id} className="preview-toast" role="status"><span className="preview-toast-icon"><Icon name="check" size={16} /></span><span><strong>{toast.title}</strong><small>{toast.detail}</small></span><button aria-label="Dismiss notification" onClick={() => setToast(null)}><Icon name="close" size={13} /></button></div>;

  return <div className="demo-wrap image-search-demo" id="demo">
    <form className="memory-search-bar" role="search" onSubmit={(event) => { event.preventDefault(); if (results[0] && ready) setSelected(results[0]); }}><Icon name="search" size={22} /><input ref={searchRef} aria-label="Search the sample memories" placeholder="Search your memories…" value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => { if (event.key === "ArrowDown") { event.preventDefault(); document.querySelector<HTMLButtonElement>(".image-search-demo .image-card")?.focus(); } }} />{query ? <button type="button" aria-label="Clear search" className="icon-button" onClick={() => { setQuery(""); searchRef.current?.focus(); }}><Icon name="close" size={17} /></button> : <kbd>⌘ K</kbd>}</form>
    <div className="try-queries"><span>Try:</span>{["softer palette", "matcha", "connection refused"].map((value) => <button key={value} onClick={() => setQuery(value)}>{value}</button>)}</div>
    <div className="image-search-heading"><span role="status" aria-live="polite">{results.length} {results.length === 1 ? "image" : "images"}</span><button className="button button-dark button-small" onClick={() => setCapturePreview(true)} disabled={!ready}>{captured ? "Try the sample capture" : "Take a sample screenshot"}<Icon name="plus" size={14} /></button></div>
    <div className="memory-results image-grid">{results.map((item) => <button className="memory-result image-card" key={item.id} onClick={() => setSelected(item)} aria-label={`Open memory: ${item.title}`} disabled={!ready}><div className="memory-thumb image-art"><MemoryArtwork item={item} /><span className="memory-note-count" key={notesFor(item).length}><Icon name="pin" size={11} />{notesFor(item).length} {notesFor(item).length === 1 ? "note" : "notes"}</span><span className="memory-open-hint"><Icon name="plus" size={14} /> Add context</span></div><div className="memory-result-copy"><strong>{item.title}</strong><small>{item.location}<Icon name="diagonal" size={12} /></small></div></button>)}</div>
    {!results.length && <div className="empty-state"><Icon name="search" size={26} /><strong>No matching sample memories.</strong><span>Try “checkout,” “matcha,” or words from a note you saved.</span><button onClick={() => setQuery("")}>Show all memories <Icon name="arrow" size={15} /></button></div>}
    <p className="image-search-footer"><Icon name="lock" size={12} /> Demo images. Real interactions. Your edits stay in this browser.</p>
    <dialog ref={dialogRef} className="image-dialog memory-dialog spatial-dialog" onClick={(event) => { if (event.target === event.currentTarget) dialogRef.current?.close(); }} onClose={() => { setSelected(null); setCapturePreview(false); }} aria-labelledby="preview-title">
      {capturePreview ? <div className="sample-capture-preview"><div className="annotation-header"><div><span className="eyebrow">01 / TAKE A PRETEND SCREENSHOT</span><h2 id="preview-title">Something worth keeping.</h2></div><button className="dialog-close icon-button" aria-label="Close capture preview" onClick={() => dialogRef.current?.close()}><Icon name="close" /></button></div><div className="sample-browser"><div className="sample-browser-bar"><span className="traffic-lights" aria-hidden="true"><i /><i /><i /></span><span><Icon name="lock" size={11} /> example.com/shop</span></div><MemoryArtwork item={demoItems[0]} /></div><div className="sample-capture-actions"><p>A sample page, not your real screen. Next: highlight some text and add a thought.</p><button className="button button-dark" onClick={captureScreenshot}>Capture screenshot <Icon name="monitor" size={16} /></button></div></div> : selected && <MemoryAnnotator key={selected.id} item={selected} annotations={notesFor(selected)} onChange={saveAnnotations} onClose={() => dialogRef.current?.close()} onSearch={returnToSearch} />}
      {(selected || capturePreview) && toastView}
    </dialog>
    {!selected && !capturePreview && toastView}
  </div>;
}
