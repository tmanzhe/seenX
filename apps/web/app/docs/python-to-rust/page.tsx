import type { Metadata } from "next";
import { DocArticle } from "../../../components/doc-article";
import { learningPages } from "../../../lib/learning-pages";
export const metadata: Metadata = { title: "From Python to Rust", alternates: { canonical: "/learning/python-to-rust" } };
// Preserve existing bookmarks while navigation points to the Learning section.
export default function LegacyLearningGuide() { return <DocArticle page={learningPages[0]} learning />; }
