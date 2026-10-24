import type { ReactNode } from "react";
import { DocsShell } from "../../components/docs-shell";
import { docsSearchEntries } from "../../lib/docs";
import { learningPages } from "../../lib/learning-pages";
import { plainText } from "../../lib/doc-content";
import { buildJournal, learningConcepts } from "../../lib/learning";

const searchEntries = [...docsSearchEntries, ...learningPages.map((page) => ({ href: `/learning/${page.slug}`, title: page.title, description: page.description, group: "Learning", keywords: plainText(page.content) })), { href: "/learning", title: "Learning overview", description: "Experiments, concepts, build journal, and personal notes.", group: "Learning", keywords: [...buildJournal.map((entry) => entry.detail), ...learningConcepts.map((entry) => entry.meaning)].join(" ") }];

export default function DocsLayout({ children }: { children: ReactNode }) {
  return <DocsShell searchEntries={searchEntries}>{children}</DocsShell>;
}
