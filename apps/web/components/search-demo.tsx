"use client";

import { useEffect, useRef, useState } from "react";
import type { DemoItem } from "../lib/demo";
import { demoItems, searchDemo } from "../lib/demo";
import { Icon } from "./icon";

function Artwork({ item }: { item: DemoItem }) {
  if (item.image) return <img src={item.image} alt={item.title} loading="lazy" />;
  if (item.id === "terminal") return <div className="terminal-art"><div className="terminal-label">~/projects/another-good-idea</div><span className="terminal-green">$ npm run dev</span><br /><br /><span className="terminal-muted">connecting to localhost:5432…</span><br /><span className="terminal-red">Error: connection refused</span><br /><span className="terminal-muted">ECONNREFUSED 127.0.0.1:5432</span><br /><br /><span className="terminal-green">❯ <span className="cursor">_</span></span></div>;
  return <div className="menu-art"><span className="menu-stamp">喫茶</span><strong>GOOD THINGS,<br />SLOWLY.</strong><span>THE LITTLE CAFÉ · SAMPLE MENU</span><div><span>Matcha latte</span><span>¥550</span></div><div><span>Pour-over coffee</span><span>¥480</span></div></div>;
}

export function SearchDemo() {
  const [query, setQuery] = useState("");
  const [collection, setCollection] = useState("all");
  const [kind, setKind] = useState("all");
  const [selected, setSelected] = useState<DemoItem | null>(null);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const results = searchDemo(query, collection, kind);

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") { event.preventDefault(); searchRef.current?.focus(); }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  useEffect(() => {
    if (selected) dialogRef.current?.showModal();
  }, [selected]);

  function openItem(item: DemoItem) { setSelected(item); }

  return (
    <div className="demo-wrap" id="demo">
      <div className="floating-note"><span className="note-arrow">↙</span> Go on, try remembering something.</div>
      <div className="desktop-window">
        <div className="window-bar"><div className="traffic-lights" aria-hidden="true"><i /><i /><i /></div><span>seenX</span><span aria-hidden="true" /></div>
        <div className="desktop-body">
          <aside className="demo-sidebar" aria-label="Demo library filters">
            <div className="sidebar-heading">YOUR LIBRARY</div>
            {([{ value: "all", label: "All images", icon: "image" }, { value: "screenshot", label: "Screenshots", icon: "monitor" }, { value: "photo", label: "Photographs", icon: "image" }] as const).map(({ value, label, icon }) => <button key={value} className={`sidebar-link ${kind === value ? "active" : ""}`} onClick={() => setKind(value)} aria-pressed={kind === value}><Icon name={icon} size={16} />{label}<span>{value === "all" ? demoItems.length : demoItems.filter((item) => item.kind === value).length}</span></button>)}
            <div className="sidebar-heading folders-heading">SAMPLE FOLDERS</div><div className="sidebar-folder"><Icon name="folder" size={15} /> Screenshots</div><div className="sidebar-folder"><Icon name="folder" size={15} /> Little adventures</div>
            <div className="sidebar-device"><span className="device-icon"><Icon name="monitor" size={18} /></span><div>On your Mac<span>That’s the idea.</span></div><Icon name="lock" size={14} /></div>
          </aside>
          <div className="demo-main">
            <div className="search-field"><Icon name="search" size={21} /><input ref={searchRef} aria-label="Search the sample library" placeholder="Describe what you remember…" value={query} onChange={(event) => setQuery(event.target.value)} /><kbd>⌘ K</kbd>{query && <button aria-label="Clear search" className="icon-button" onClick={() => setQuery("")}><Icon name="close" size={16} /></button>}</div>
            <div className="demo-toolbar"><div><span className="demo-title">{query ? "A few familiar things" : "Your little collection"}</span><span className="result-count" role="status" aria-live="polite">{results.length} {results.length === 1 ? "image" : "images"}</span></div><label className="collection-filter"><Icon name="pin" size={13} /><span className="sr-only">Filter sample collection</span><select value={collection} onChange={(event) => setCollection(event.target.value)}><option value="all">Everywhere</option><option>Alpine trip</option><option>Coastal trip</option><option>City trip</option><option>Work</option></select></label></div>
            <div className="image-grid">{results.map((item) => <button className="image-card" key={item.id} onClick={() => openItem(item)} aria-label={`Preview ${item.title}`}><div className="image-art"><Artwork item={item} /><span className="image-type"><Icon name={item.kind === "photo" ? "image" : "monitor"} size={12} /></span><span className="image-expand"><Icon name="diagonal" size={15} /></span></div><div className="image-caption"><strong>{item.title}</strong><span>{item.file}</span></div></button>)}</div>
            {!results.length && <div className="empty-state"><Icon name="search" size={30} /><strong>That memory isn’t in this sample.</strong><span>Try “mountains,” “terminal,” or “café,” or clear your filters.</span><button onClick={() => { setQuery(""); setCollection("all"); setKind("all"); }}>Show the whole collection <Icon name="arrow" size={15} /></button></div>}
            <div className="demo-status"><span><span className="status-dot" /> Sample library · interactive preview</span><span>Try a memory below.</span></div>
          </div>
        </div>
      </div>
      <div className="try-queries"><span>Try a little nudge:</span>{["green mountains", "connection refused", "café menu"].map((value) => <button key={value} onClick={() => { setQuery(value === "café menu" ? "cafe menu" : value); setKind("all"); setCollection("all"); }}>{value}<Icon name="diagonal" size={12} /></button>)}</div>
      <dialog ref={dialogRef} className="image-dialog" onClick={(event) => { if (event.target === event.currentTarget) dialogRef.current?.close(); }} onClose={() => setSelected(null)} aria-labelledby="preview-title">
        {selected && <><button className="dialog-close icon-button" aria-label="Close image preview" onClick={() => dialogRef.current?.close()}><Icon name="close" /></button><div className="dialog-art"><Artwork item={selected} /></div><div className="dialog-info"><span className="eyebrow">SAMPLE RECORD</span><h2 id="preview-title">{selected.title}</h2><dl><div><dt>Filename</dt><dd>{selected.file}</dd></div><div><dt>Collection</dt><dd>{selected.location}</dd></div><div><dt>Type</dt><dd>{selected.kind}</dd></div></dl><p>Sample image and illustrative metadata.</p></div></>}
      </dialog>
    </div>
  );
}
