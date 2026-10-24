import type { Metadata } from "next";
import { overviewPage } from "../../lib/docs";
import { DocArticle } from "../../components/doc-article";

export const metadata: Metadata = { title: "Documentation" };

export default function Docs() {
  return <DocArticle page={overviewPage} />;
}
