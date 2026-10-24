import Link from "next/link";
import type { DocPage } from "../lib/docs";
import { prepareArticle } from "../lib/doc-content";
import { docNavigation } from "../lib/docs-navigation";
import { PageOutline } from "./page-outline";
import { Icon } from "./icon";

export function DocArticle({ page }: { page: DocPage }) {
  const href = page.slug ? `/docs/${page.slug}` : "/docs";
  const group = docNavigation.find((section) => section.links.some((link) => link.href === href));
  const links = docNavigation.flatMap((section) => section.links);
  const index = links.findIndex((link) => link.href === href);
  const previous = links[index - 1];
  const next = links[index + 1];
  const { body, headings } = prepareArticle(page.content);
  return (
    <div className="docs-article-layout">
      <main className="docs-main" id="main">
        <span className="docs-breadcrumb">{group?.title ?? "Documentation"}</span>
        <h1>{page.title}</h1>
        <p className="docs-description">{page.description}</p>
        {page.status && <div className="doc-status"><span className="status-dot" />{page.status}</div>}
        <article className="prose">{body}</article>
        <nav className="docs-pagination" aria-label="Previous and next documentation pages">
          {previous ? <Link href={previous.href}><Icon name="arrow" size={16} style={{ transform: "rotate(180deg)" }} /><span>Previous<strong>{previous.title}</strong></span></Link> : <span />}
          {next && <Link href={next.href}><span>Next<strong>{next.title}</strong></span><Icon name="arrow" size={16} /></Link>}
        </nav>
      </main>
      <PageOutline headings={headings} />
    </div>
  );
}
