import type { MetadataRoute } from "next";
import { docPages } from "../lib/docs";

export const dynamic = "force-static";

export default function sitemap(): MetadataRoute.Sitemap {
  const origin = "https://seenx-lovat.vercel.app";
  return ["", "/docs", "/learning", "/support", ...docPages.map((page) => `/docs/${page.slug}`)].map((path) => ({ url: origin + path, changeFrequency: "monthly", priority: path === "" ? 1 : path === "/docs/roadmap" ? .9 : .7 }));
}
