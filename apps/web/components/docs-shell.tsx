"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { searchDocumentation, type DocSearchEntry } from "../lib/docs-navigation";
import { DocsNav } from "./docs-nav";
import { Brand } from "./site-chrome";
import { Icon } from "./icon";
import { ThemeToggle } from "./theme-toggle";
import { SoundToggle } from "./sound-controls";

export function DocsShell({ children, searchEntries }: { children: ReactNode; searchEntries: DocSearchEntry[] }) {
  const pathname = usePathname();
  const router = useRouter();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(0);
  const dialog = useRef<HTMLDialogElement>(null);
  const isLearning = pathname.startsWith("/learning") || pathname === "/docs/learning" || pathname === "/docs/python-to-rust";
  const results = searchDocumentation(searchEntries.filter((entry) => entry.href.startsWith("/learning") === isLearning), query);

  function closeSearch() { dialog.current?.close(); setQuery(""); setSelected(0); }

  useEffect(() => {
    const shortcut = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        if (!dialog.current?.open) dialog.current?.showModal();
      }
    };
    window.addEventListener("keydown", shortcut);
    return () => window.removeEventListener("keydown", shortcut);
  }, []);

  return (
    <div className="docs-site">
      <header className="docs-header">
        <div className="docs-header-main">
          <div className="docs-brand"><Brand /><span className="docs-brand-divider" /><Link href={isLearning ? "/learning" : "/docs"}>{isLearning ? "learning" : "docs"}</Link></div>
          <button className="docs-search-trigger" onClick={() => dialog.current?.showModal()}><Icon name="search" size={17} /><span>{isLearning ? "Search learning…" : "Search documentation…"}</span><kbd>⌘ K</kbd></button>
          <ThemeToggle /><SoundToggle /><Link href="/" className="docs-back-link">Back to seenX <Icon name="diagonal" size={14} /></Link>
        </div>
        <div className="docs-header-tabs">
          <nav aria-label="Site sections"><Link href="/docs" aria-current={!isLearning ? "page" : undefined}>Documentation</Link><Link href="/learning" aria-current={isLearning ? "page" : undefined}>Learning</Link></nav>
          <span className="docs-build-status"><span className="status-dot" /> In development</span>
        </div>
      </header>
      <button className="docs-mobile-toggle" onClick={() => setMobileOpen(!mobileOpen)} aria-expanded={mobileOpen} aria-controls="docs-navigation"><Icon name={mobileOpen ? "close" : "menu"} size={17} /> Browse {isLearning ? "learning" : "documentation"} <span aria-hidden="true">{mobileOpen ? "−" : "+"}</span></button>
      <div className="docs-shell-grid"><DocsNav open={mobileOpen} onNavigate={() => setMobileOpen(false)} /><div className="docs-page-slot">{children}</div></div>
      <dialog className="docs-search-dialog" ref={dialog} aria-label={isLearning ? "Search learning" : "Search documentation"} onClose={() => { setQuery(""); setSelected(0); }} onClick={(event) => { if (event.target === event.currentTarget) closeSearch(); }}>
        <div className="docs-search-input"><Icon name="search" size={21} /><input autoFocus aria-label={isLearning ? "Search learning" : "Search documentation"} value={query} placeholder={isLearning ? "Search experiments, concepts, notes…" : "Search reference, setup, integrations…"} onChange={(event) => { setQuery(event.target.value); setSelected(0); }} onKeyDown={(event) => {
          if (event.key === "ArrowDown") { event.preventDefault(); setSelected((index) => Math.max(0, Math.min(index + 1, results.length - 1))); }
          if (event.key === "ArrowUp") { event.preventDefault(); setSelected((index) => Math.max(index - 1, 0)); }
          if (event.key === "Enter" && results[selected]) { event.preventDefault(); router.push(results[selected].href); closeSearch(); }
        }} /><button onClick={closeSearch} className="icon-button" aria-label="Close search"><Icon name="close" size={18} /></button></div>
        <div className="docs-search-results" aria-live="polite"><div className="docs-search-hint">{query ? `${results.length} matching pages` : "START EXPLORING"}</div>{results.map((entry, index) => <Link key={entry.href} href={entry.href} className="docs-search-result" data-selected={selected === index} onClick={closeSearch} onFocus={() => setSelected(index)}><span className="docs-search-result-icon"><Icon name={entry.href.includes("agent") ? "terminal" : "code"} size={18} /></span><span><small>{entry.group}</small><strong>{entry.title}</strong><span>{entry.description}</span></span><Icon name="arrow" size={16} /></Link>)}{!results.length && <p className="docs-search-empty">No matching pages. Try “embeddings,” “agents,” or “Python.”</p>}</div>
        <div className="docs-search-footer"><span>↑ ↓ to navigate</span><span>↵ to open</span><span>esc to close</span></div>
      </dialog>
    </div>
  );
}
