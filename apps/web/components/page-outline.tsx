"use client";

import { useEffect, useState } from "react";

export function PageOutline({ headings }: { headings: { id: string; title: string }[] }) {
  const [active, setActive] = useState(headings[0]?.id);
  useEffect(() => {
    setActive(headings[0]?.id);
    const observer = new IntersectionObserver((entries) => {
      for (const entry of entries) if (entry.isIntersecting) setActive(entry.target.id);
    }, { rootMargin: "-140px 0px -60% 0px" });
    for (const { id } of headings) { const node = document.getElementById(id); if (node) observer.observe(node); }
    return () => observer.disconnect();
  }, [headings]);
  return <aside className="page-outline"><span>On this page</span><nav aria-label="On this page">{headings.map(({ id, title }) => <a key={id} href={`#${id}`} aria-current={active === id ? "location" : undefined}>{title}</a>)}</nav></aside>;
}
