import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { docPages } from "../../../lib/docs";
import { DocArticle } from "../../../components/doc-article";

export const dynamicParams = false;
export function generateStaticParams() { return docPages.map(({ slug }) => ({ slug })); }

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const doc = docPages.find((page) => page.slug === slug);
  return { title: doc?.title ?? "Page not found", description: doc?.description };
}

export default async function Doc({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const index = docPages.findIndex((page) => page.slug === slug);
  if (index < 0) notFound();
  return <DocArticle page={docPages[index]} />;
}
