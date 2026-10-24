import type { ReactNode } from "react";
import { DocsShell } from "../../components/docs-shell";
import { docsSearchEntries } from "../../lib/docs";

export default function DocsLayout({ children }: { children: ReactNode }) {
  return <DocsShell searchEntries={docsSearchEntries}>{children}</DocsShell>;
}
