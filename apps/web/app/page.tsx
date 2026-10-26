import Link from "next/link";
import { Icon } from "../components/icon";
import { SearchDemo } from "../components/search-demo";
import { AsciiMemory } from "../components/ascii-memory";
import { LandingMotion } from "../components/landing-motion";
import { HeroMemoryScene } from "../components/hero-memory-scene";

export default function Home() {
  return <main id="main" className="landing-page">
    <LandingMotion />
    <section className="hero hero-editorial premium-hero">
      <AsciiMemory />
      <div className="hero-copy">
        <h1>Save what matters.<br />Remember <em>why.</em></h1>
        <p className="hero-description">Screenshots, ideas, and the thoughts that make them yours.<br className="hero-desktop-break" /> Find your way back—in your own words.</p>
        <div className="hero-actions"><a href="#demo" className="button button-orange">Try the hands-on demo <Icon name="arrow" size={17} /></a><Link href="/docs" className="text-link">About seenX <Icon name="diagonal" size={15} /></Link></div>
      </div>
      <div className="premium-scene-wrap"><HeroMemoryScene /></div>
    </section>

    <section className="demo-section" aria-labelledby="demo-heading"><div className="demo-intro"><h2 id="demo-heading">Try the hands-on demo.</h2></div><SearchDemo /></section>

    <section className="assistant-section section-container" id="assistant-bridge" aria-labelledby="assistant-heading"><div className="assistant-copy"><h2 id="assistant-heading">Your context,<br /><em>where you work.</em></h2><p>Bring selected images, highlights, and notes into your assistant’s next task.</p><Link href="/docs/agents" className="text-link">Explore the assistant bridge <Icon name="arrow" size={15} /></Link></div><div className="assistant-concept"><div className="assistant-concept-top"><span className="brand-symbol" aria-hidden="true"><i /><i /><i /><i /></span><span>seenX × your assistant</span><span className="concept-badge">Connection concept</span></div><div className="assistant-prompt">Pull my screenshots tagged “checkout flow” and build a prototype matching my notes.</div><div className="assistant-tool"><Icon name="search" size={14} /><span>Search selected memories</span><Icon name="lock" size={13} /></div><div className="assistant-memory"><div className="assistant-memory-art"><Icon name="image" size={26} /></div><div><strong>A checkout worth remembering</strong><span>“Keep the spacing. Try a softer palette.”</span><small>Image + your note + source</small></div></div></div></section>

    <section className="portability-section section-container" id="take-it-with-you" aria-labelledby="portability-heading"><div className="portability-copy"><h2 id="portability-heading">New laptop.<br /><em>Same memories.</em></h2><p>The transfer plan carries your images, notes, and highlights together—or just the context, ready to reconnect to your originals.</p><Link href="/docs/portability" className="text-link">Explore library transfer <Icon name="arrow" size={15} /></Link></div><div className="portability-visual"><span className="concept-badge">Planned for V1</span><div className="portability-route" aria-label="A library archive moves saved context from an old Mac to a new Mac"><div><Icon name="monitor" size={30} /><span>Your old Mac</span></div><Icon name="arrow" size={17} /><div className="portability-archive"><Icon name="folder" size={30} /><span>Your library</span></div><Icon name="arrow" size={17} /><div><Icon name="monitor" size={30} /><span>Your next Mac</span></div></div></div></section>

    <section className="faq-section section-container"><div><h2>A few details.</h2></div><div className="faq-list">{[
      ["What can I use today?", "The browser preview: capture a sample screenshot, highlight text or an area, add notes, search, and export JSON. The desktop app, assistant connection, and library transfer are in development."],
      ["Does my data stay local?", "This preview uses sample images and saves your edits in this browser. It does not access your Mac. The desktop design keeps the library and search local; sharing selected context with a cloud assistant sends that content to its provider."],
      ["Do I need to organize everything or add notes?", "No. Notes and collections are optional. Add context when it helps explain why something mattered; the intended desktop app also searches appearance, visible text, and available source details."],
    ].map(([question, answer]) => <details key={question}><summary>{question}<span aria-hidden="true">+</span></summary><p>{answer}</p></details>)}</div></section>
  </main>;
}
