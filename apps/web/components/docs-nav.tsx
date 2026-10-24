"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { docNavigation } from "../lib/docs-navigation";

export function DocsNav({ open, onNavigate }: { open: boolean; onNavigate: () => void }) {
  const pathname = usePathname();
  const current = pathname === "/learning" ? "/docs/learning" : pathname;
  return (
    <aside className="docs-sidebar" data-open={open} id="docs-navigation">
      <nav aria-label="Documentation sections">
        {docNavigation.map((group) => (
          <div className="docs-nav-group" key={group.title}>
            <h2>{group.title}</h2>
            {group.links.map(({ href, title }) => (
              <Link key={href} href={href} aria-current={current === href ? "page" : undefined} onClick={onNavigate}>{title}</Link>
            ))}
          </div>
        ))}
      </nav>
      <Link className="docs-sidebar-project" href="/docs/roadmap" onClick={onNavigate}><span className="status-dot" /> Follow the build <span aria-hidden="true">↗</span></Link>
    </aside>
  );
}
