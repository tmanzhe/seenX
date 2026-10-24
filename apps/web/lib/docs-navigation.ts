export type DocLink = { href: string; title: string };
export type DocGroup = { title: string; links: DocLink[] };
export type DocSearchEntry = DocLink & { description: string; group: string; keywords: string };

export const docNavigation: DocGroup[] = [
  { title: "Get started", links: [
    { href: "/docs", title: "What is seenX?" },
    { href: "/docs/getting-started", title: "Local development" },
  ] },
  { title: "Use cases", links: [
    { href: "/docs/personal-search", title: "For your own memory" },
    { href: "/docs/agent-workflows", title: "For your AI agents" },
    { href: "/docs/agents", title: "Agent integration" },
  ] },
  { title: "How it works", links: [
    { href: "/docs/how-search-works", title: "Search & metadata" },
    { href: "/docs/privacy", title: "Privacy & local data" },
  ] },
  { title: "Reference", links: [
    { href: "/docs/ontology", title: "Entities & relationships" },
    { href: "/docs/architecture", title: "Architecture" },
  ] },
  { title: "The project", links: [
    { href: "/docs/roadmap", title: "Roadmap" },
    { href: "/docs/open-source", title: "Open source & support" },
  ] },
];

export const learningNavigation: DocGroup[] = [
  { title: "Learning", links: [
    { href: "/learning", title: "Learning overview" },
    { href: "/learning/python-to-rust", title: "Python → Rust" },
    { href: "/learning/ontology", title: "Ontology experiment" },
  ] },
  { title: "Notebook", links: [
    { href: "/learning#build-journal", title: "Build journal" },
    { href: "/learning#concepts", title: "Concepts" },
    { href: "/learning#my-notes", title: "Personal notes" },
  ] },
];

export function searchDocumentation(entries: DocSearchEntry[], query: string) {
  const normalize = (value: string) => value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  const tokens = normalize(query).trim().split(/\s+/).filter(Boolean);
  return entries
    .map((entry, order) => {
      const title = normalize(entry.title);
      const text = normalize(`${entry.title} ${entry.description} ${entry.keywords}`);
      return { entry, order, matches: tokens.every((token) => text.includes(token)), score: tokens.reduce((sum, token) => sum + (title.includes(token) ? 3 : 0), 0) };
    })
    .filter(({ matches }) => matches)
    .sort((a, b) => b.score - a.score || a.order - b.order)
    .slice(0, 8)
    .map(({ entry }) => entry);
}
