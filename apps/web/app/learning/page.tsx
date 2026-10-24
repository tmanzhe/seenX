import type { Metadata } from "next";
import DocsLayout from "../docs/layout";
import { LearningArticle } from "../../components/learning-article";

export const metadata: Metadata = { title: "Learning notes" };

// Preserve existing bookmarks and the same-origin browser notebook.
export default function LearningAlias() {
  return <DocsLayout><LearningArticle /></DocsLayout>;
}
