import type { Metadata } from "next";
import { LearningArticle } from "../../../components/learning-article";

export const metadata: Metadata = {
  title: "Learning notes",
  description: "The build journal, concepts, experiments, and personal notebook behind seenX.",
};

export default function Learning() { return <LearningArticle />; }
