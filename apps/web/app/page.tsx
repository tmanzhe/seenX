import Link from "next/link";
import { Icon } from "../components/icon";
import { SearchDemo } from "../components/search-demo";
import { UseCases } from "../components/use-cases";

export default function Home() {
  return (
    <main id="main">
      <section className="hero">
        <div className="hero-eyebrow"><span className="status-dot" /> YOUR VISUAL MEMORY, CLOSE AT HAND.</div>
        <h1>You’ve seen it.<br />Find it <em>again.</em></h1>
        <p className="hero-description">The screenshot. The place. That one thing you saved.<br className="desktop-break" /> Visual memory for you—and the AI agents you build.</p>
        <div className="hero-actions"><a href="#demo" className="button button-orange">Explore the preview <Icon name="arrow" size={17} /></a><Link href="/docs" className="text-link">See what we’re building <Icon name="diagonal" size={15} /></Link></div>
        <div className="hero-footnote"><Icon name="monitor" size={14} /> Local engine first <span>·</span> Free, with optional support <span>·</span> In development</div>
      </section>
      <div className="demo-section"><SearchDemo /></div>

      <UseCases />

      <section className="ways-section section-container" id="how-it-works">
        <div className="section-intro"><span className="eyebrow">YOUR MEMORY ISN’T A FILENAME</span><h2>Remember it your way.</h2><p>Some things you remember word for word.<br />Others are just a feeling, a place, a little detail.</p></div>
        <div className="ways-grid">
          <article><span className="step-number">01 / THE WORDS</span><div className="word-visual"><span>ERROR: <mark>connection refused</mark></span><span className="ocr-label"><Icon name="search" size={12} /> Text inside your screenshots</span></div><h3>“That terminal error.”</h3><p>Search the words you remember seeing, even when the filename tells you nothing.</p></article>
          <article><span className="step-number">02 / THE FEELING</span><div className="feeling-visual"><img src="/images/mountain-light.jpg" alt="Sunlight spilling across a mountain landscape" loading="lazy" /><span>blue sky, green mountains</span></div><h3>“Somewhere like this.”</h3><p>A color, a scene, a little detail. Start with a description.</p></article>
          <article><span className="step-number">03 / THE DETAILS</span><div className="details-visual"><div><Icon name="pin" size={17} /><span>Alpine trip</span><Icon name="check" size={13} /></div><div><span className="calendar-icon">12</span><span>Last summer</span></div><span className="metadata-note">A little context goes a long way.</span></div><h3>“On that trip last summer.”</h3><p>Narrow it down by the place, date, or collection you have in mind.</p></article>
        </div>
      </section>

      <section className="local-section section-container" id="local-first">
        <div className="local-copy"><span className="eyebrow">A SMALL APP. A PERSONAL SPACE.</span><h2>Your memories.<br /><em>Your machine.</em></h2><p>The goal is simple: your selected folders, a local index, and search that works without sending your images to an AI service.</p><ul><li><Icon name="check" size={16} /> You choose the folders.</li><li><Icon name="check" size={16} /> Models run on your device.</li><li><Icon name="check" size={16} /> Your index stays under your control.</li></ul><Link href="/docs/privacy" className="text-link">Read the privacy approach <Icon name="arrow" size={15} /></Link></div>
        <div className="local-visual" aria-label="Concept diagram showing selected folders connecting to a local index"><span className="diagram-caption">THE INTENDED FLOW</span><div className="folder-stack"><div><Icon name="folder" /><span>Screenshots</span></div><div><Icon name="folder" /><span>Little adventures</span></div><div><Icon name="folder" /><span>Things worth keeping</span></div></div><div className="connection-line" /><div className="index-node"><span className="brand-symbol" aria-hidden="true"><i /><i /><i /><i /></span><div>seenX index<span>Words + meaning + metadata</span></div><Icon name="lock" size={18} /></div><div className="device-boundary"><Icon name="monitor" size={15} /> This boundary is your Mac.</div></div>
      </section>

      <section className="agents-section"><div className="section-container agents-inner"><div><span className="eyebrow">FOR THE AGENTS YOU BUILD</span><h2>A useful memory.<br />A better <em>starting point.</em></h2><p>The diagram behind a coding task. The chart behind an answer. The references behind an idea. Give your local agent a way to find them.</p><Link href="/docs/agent-workflows" className="text-link">See the agent use cases <Icon name="arrow" size={16} /></Link></div><div className="agent-diagram"><div className="agent-title"><Icon name="terminal" size={16} /><span>CONTEXT, WHEN IT’S USEFUL</span><span className="agent-planned">PLANNED</span></div><div className="agent-message">“Find the architecture diagram I saved.”</div><div className="agent-flow"><span>Your agent</span><span>↓</span><span className="adapter-node">seenX</span><span>↓</span><span>The reference it needed</span></div><div className="agent-evidence"><Icon name="image" size={16} /><div>The image. The words. The source.<span>From the library you choose.</span></div><Icon name="check" size={16} /></div></div></div></section>

      <section className="evidence-section section-container" aria-labelledby="agent-bottlenecks">
        <div className="section-intro"><span className="eyebrow">THE CONTEXT BOTTLENECK</span><h2 id="agent-bottlenecks">Find the evidence.<br />Then let your agent work.</h2><p>An agent needs a way to locate the right saved image.<br />seenX is exploring a reusable local retrieval layer.</p></div>
        <div className="workflow-table-wrap"><table className="workflow-table"><caption>Workflow comparison · proposed capabilities, not benchmark results</caption><thead><tr><th scope="col">Approach</th><th scope="col">Useful for</th><th scope="col">Bottleneck</th></tr></thead><tbody><tr><th scope="row">Attach an image</th><td>Inspecting a reference you already found</td><td>You still have to locate the file</td></tr><tr><th scope="row">Search files or OCR text</th><td>Known filenames and visible phrases</td><td>Visual descriptions need another signal</td></tr><tr><th scope="row">Indexed retrieval</th><td>Finding relevant items across a collection</td><td>Needs indexing, updates, and quality checks</td></tr><tr><th scope="row">seenX direction</th><td>Local text + visual search + traceable relationships</td><td>Prototype and evaluation still pending</td></tr></tbody></table></div>
        <p className="evidence-note">Agents can already use search tools and indexed retrieval. Our question is whether a local image-focused index makes selected visual evidence easier to recover. <a href="https://developers.openai.com/api/docs/guides/tools-file-search" target="_blank" rel="noreferrer">Example: hosted file retrieval ↗</a></p>
        <div className="section-intro"><span className="eyebrow">MEASURE BEFORE WE CLAIM</span><h2>Useful numbers. Real experiments.</h2><p>No speedup or accuracy claims yet. These are the statistics<br />we will publish with the dataset, hardware, and method.</p></div>
        <div className="measurement-grid">{[
          ["Top-five hit rate", "Queries with an acceptable image in the first five results."],
          ["Warm query latency", "Time to retrieve results after the model and index are loaded."],
          ["Indexing cost", "Time, memory, and storage needed to make a collection searchable."],
          ["Relationship quality", "Retrieval gains, false associations, and effort spent correcting suggestions."],
        ].map(([title, description]) => <article key={title}><span className="planned-label">Not measured yet</span><h3>{title}</h3><p>{description}</p></article>)}</div>
        <p className="evidence-note">Compare OCR, visual, hybrid, and relationship-assisted retrieval on the same labeled queries. Agent tool calls and returned context size are later workflow measures—not promised savings.</p>
        <Link href="/learning/python-to-rust" className="text-link">Follow the evaluation plan <Icon name="arrow" size={16} /></Link>
      </section>
      <section className="build-path section-container"><span className="eyebrow">LEARN IT. PROVE IT. BUILD IT.</span><h2>Python first.<br />Rust for the engine.</h2><p>Learn OCR, embeddings, metadata, and ontology through small Python experiments. Measure what works, then implement it in Rust. A native Mac interface comes later.</p><div className="docs-flow-strip"><span>Python proof of concept</span><span aria-hidden="true">→</span><span>Measured results</span><span aria-hidden="true">→</span><span>Rust engine</span></div><Link href="/learning/ontology" className="text-link">Explore ontology and model-assisted learning <Icon name="arrow" size={16} /></Link></section>

      <section className="open-section section-container" id="open-source"><span className="eyebrow">A SMALL TOOL. A SHARED PROJECT.</span><h2>Useful should be<br /><em>for everyone.</em></h2><p>Free and open source is the plan.<br className="desktop-break" /> Support it if it helps you.</p><div className="open-actions"><Link href="/docs/roadmap" className="button button-dark">Follow the build <Icon name="arrow" size={16} /></Link><Link href="/support" className="text-link">Support the project <Icon name="heart" size={16} /></Link></div></section>

      <section className="faq-section section-container"><div><span className="eyebrow">A FEW GOOD QUESTIONS</span><h2>Before you ask.</h2></div><div className="faq-list">{[
        ["What is seenX for?", "Finding the screenshots, photos, and visual references you remember saving."],
        ["Can my AI agent use it?", "Agent access is planned, so self-hosted agents can retrieve useful context from your selected library."],
        ["Is it designed to run locally?", "Yes. Local processing and control over your own files are central to the design."],
        ["When can I try it?", "seenX is in development. Explore the preview and follow the build in the docs."],
      ].map(([question, answer]) => <details key={question}><summary>{question}<span aria-hidden="true">+</span></summary><p>{answer}</p></details>)}</div></section>
    </main>
  );
}
