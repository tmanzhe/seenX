import type { Metadata } from "next";
import type { ReactNode } from "react";
import { SiteFrame } from "../components/site-frame";
import { SoundProvider } from "../components/sound-controls";
import { productDescription } from "../lib/product";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://seenx-lovat.vercel.app"),
  title: { default: "seenX — Save what matters. Remember why.", template: "%s — seenX" },
  description: productDescription,
  openGraph: { title: "seenX — Save what matters. Remember why.", description: productDescription, siteName: "seenX", type: "website", locale: "en_US" },
  twitter: { card: "summary", title: "seenX — Save what matters. Remember why.", description: productDescription },
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
