import type { Metadata } from "next";
import { notFound } from "next/navigation";
import DocsLayout from "../../docs/layout";
import { learningPages } from "../../../lib/learning-pages";
import { DocArticle } from "../../../components/doc-article";

export const dynamicParams = false;
export function generateStaticParams() { return learningPages.map(({ slug }) => ({ slug })); }
export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const page = learningPages.find((entry) => entry.slug === slug);
  return { title: page?.title ?? "Page not found", description: page?.description };
}
export default async function LearningGuide({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const page = learningPages.find((entry) => entry.slug === slug);
  if (!page) notFound();
  return <DocsLayout><DocArticle page={page} learning /></DocsLayout>;
}
