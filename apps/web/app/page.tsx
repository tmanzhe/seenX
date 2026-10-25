import Link from "next/link";
import { Icon } from "../components/icon";
import { SearchDemo } from "../components/search-demo";
import { AsciiMemory } from "../components/ascii-memory";
import { UseCases } from "../components/use-cases";
import { LandingMotion } from "../components/landing-motion";

export default function Home() {
  return (
    <main id="main" className="landing-page">
      <LandingMotion />
      <section className="hero hero-editorial">
        <AsciiMemory />
        <div className="hero-copy">
        <h1>Everything you saved.<br />Back in <em>context.</em></h1>
        <p className="hero-description">Find screenshots and visual references by what you remember. Give your agents a way to find them, too.</p>
        <div className="hero-actions"><a href="#demo" className="button button-orange">Explore the preview <Icon name="arrow" size={17} /></a><Link href="/docs" className="text-link">See what we’re building <Icon name="diagonal" size={15} /></Link></div>
        </div>
      </section>
      <div className="demo-section"><SearchDemo /></div>

      <UseCases />

      <section className="local-section section-container" id="local-first">
        <div className="local-copy"><span className="eyebrow">A SMALL APP. A PERSONAL SPACE.</span><h2>Your memories.<br /><em>Your machine.</em></h2><p>The goal is simple: your selected folders, a local index, and search that works without sending your images to an AI service.</p><ul><li><Icon name="check" size={16} /> You choose the folders.</li><li><Icon name="check" size={16} /> Models run on your device.</li><li><Icon name="check" size={16} /> Your index stays under your control.</li></ul><Link href="/docs/privacy" className="text-link">Read the privacy approach <Icon name="arrow" size={15} /></Link></div>
        <div className="local-visual" aria-label="Concept diagram showing selected folders connecting to a local index"><span className="diagram-caption">THE INTENDED FLOW</span><div className="folder-stack"><div><Icon name="folder" /><span>Screenshots</span></div><div><Icon name="folder" /><span>Little adventures</span></div><div><Icon name="folder" /><span>Things worth keeping</span></div></div><div className="connection-line" /><div className="index-node"><span className="brand-symbol" aria-hidden="true"><i /><i /><i /><i /></span><div>seenX index<span>Words + meaning + metadata</span></div><Icon name="lock" size={18} /></div><div className="device-boundary"><Icon name="monitor" size={15} /> This boundary is your Mac.</div></div>
      </section>

      <section className="faq-section section-container"><div><span className="eyebrow">A FEW GOOD QUESTIONS</span><h2>Before you ask.</h2></div><div className="faq-list">{[
        ["Does the preview search my own files?", "No. It searches authored sample records in your browser. It does not access your folders or run an AI model."],
        ["Will it record my screen?", "The current direction is to index images in folders you select. Continuous screen recording is outside the initial scope."],
        ["Will a connected agent keep images local?", "seenX indexing is intended to run locally. A connected agent may forward retrieved images to its model provider, depending on its configuration."],
        ["When can I try it?", "seenX is in development. Explore the preview and follow the build in the docs."],
      ].map(([question, answer]) => <details key={question}><summary>{question}<span aria-hidden="true">+</span></summary><p>{answer}</p></details>)}</div></section>
    </main>
  );
}
