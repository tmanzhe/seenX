import type { Metadata } from "next";
import type { ReactNode } from "react";
import { SiteFrame } from "../components/site-frame";
import { SoundProvider } from "../components/sound-controls";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "seenX — Find what you remember", template: "%s — seenX" },
  description: "A local-first visual memory for your Mac. Explore the early seenX concept: search screenshots and images by words, meaning, and metadata.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" data-scroll-behavior="smooth">
      <body style={{ isolation: "isolate" }}>
        <a className="skip-link" href="#main">Skip to content</a>
        <SoundProvider><SiteFrame>{children}</SiteFrame></SoundProvider>
      </body>
    </html>
  );
}
