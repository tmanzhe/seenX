import Link from "next/link";
import { Icon } from "./icon";
import { LearningNotebook } from "./learning-notebook";
import { PageOutline } from "./page-outline";
import { buildJournal, experimentSteps, learningConcepts, learningUpdated } from "../lib/learning";

export function LearningArticle() {
  return (
    <div className="docs-article-layout">
    <main id="main" className="docs-main learning-doc">
      <header className="learning-header">
        <span className="docs-breadcrumb">Build & learn</span>
        <h1>Learning notes</h1>
        <p>The build journal, experiments, concepts, and notes. One small step at a time.</p>
        <div className="learning-meta"><span><span className="status-dot" /> Learning in progress</span><span>Build notes updated <time dateTime={learningUpdated}>October 24, 2026</time></span></div>
      </header>

      <div className="learning-layout">
        <div className="learning-content">
          <section id="right-now" className="learning-section learning-now" aria-labelledby="now-heading">
            <div className="learning-section-kicker"><span className="eyebrow">01 / RIGHT NOW</span><span className="learning-badge">Experiment not started</span></div>
            <h2 id="now-heading">One question to begin with.</h2>
            <blockquote>“Can I find an image just by describing what I remember?”</blockquote>
            <p>We’ll test that in Python with my own images, before connecting a model to the app. First ten images, then a bigger collection once the pipeline works.</p>
            <div className="learning-next"><Icon name="terminal" size={21} /><div><span>NEXT BUILD STEP · AFTER REVIEW</span><h3>Set up the isolated Python project.</h3><p>Understand the environment and its two project files. Then make that one change and pause.</p></div></div>
            <div className="learning-agreement"><strong>Our pace</strong><span>Explain <span aria-hidden="true">→</span> Make one change <span aria-hidden="true">→</span> Inspect <span aria-hidden="true">→</span> Review & approve</span></div>
          </section>

          <section id="build-journal" className="learning-section" aria-labelledby="journal-heading">
            <span className="eyebrow">02 / THE BUILD JOURNAL</span>
            <h2 id="journal-heading">What we decided. And why.</h2>
            <p className="learning-section-intro">A record of our discussions so far, with plans kept separate from completed work.</p>
            <div className="learning-journal">{buildJournal.map((entry) => (
              <article key={entry.id} className="learning-entry">
                <span className="learning-entry-kind">{entry.kind}</span>
                <h3>{entry.title}</h3><p>{entry.detail}</p>
                <p className="learning-takeaway"><span>Keep in mind</span>{entry.takeaway}</p>
              </article>
            ))}</div>
          </section>

          <section id="small-steps" className="learning-section" aria-labelledby="steps-heading">
            <span className="eyebrow">03 / THE SMALL STEPS</span>
            <h2 id="steps-heading">The whole path. Only when I need it.</h2>
            <p className="learning-section-intro">Open one step at a time. These are planned milestones, not things we’ve already built.</p>
            <div className="learning-steps">{experimentSteps.map((step, index) => (
              <details key={step.title}>
                <summary><span className="learning-step-number">{String(index + 1).padStart(2, "0")}</span><span><strong>{step.title}</strong><span>{step.summary}</span></span><span className="learning-expand" aria-hidden="true">+</span></summary>
                <div className="learning-step-body"><p>{step.explanation}</p><p className="learning-done"><strong>Done when</strong>{step.done}</p></div>
              </details>
            ))}</div>
            <p className="learning-boundary">Later: OCR, metadata filters, databases, Rust integration, and the native app. They each get their own learning steps.</p>
          </section>

          <section id="concepts" className="learning-section" aria-labelledby="concepts-heading">
            <span className="eyebrow">04 / THINGS TO UNDERSTAND</span>
            <h2 id="concepts-heading">A little less jargon.</h2>
            <p className="learning-section-intro">The basic idea: turn images and a description into numbers we can compare.</p>
            <ol className="learning-flow" aria-label="Planned semantic search flow"><li><Icon name="image" size={20} /><strong>My images</strong><span>Image encoder → vectors</span></li><li><Icon name="search" size={20} /><strong>My description</strong><span>Text encoder → vector</span></li><li><Icon name="check" size={20} /><strong>Compare & rank</strong><span>The five closest matches</span></li></ol>
            <div className="learning-glossary">{learningConcepts.map(({ term, meaning }) => <details key={term}><summary>{term}<span className="learning-expand" aria-hidden="true">+</span></summary><p>{meaning}</p></details>)}</div>
            <a className="text-link learning-reference" href="https://huggingface.co/openai/clip-vit-base-patch32" target="_blank" rel="noreferrer">The CLIP baseline we’ll try <Icon name="diagonal" size={14} /></a>
          </section>

          <section id="my-notes" className="learning-section" aria-labelledby="notes-heading">
            <span className="eyebrow">05 / MY OWN NOTES</span>
            <h2 id="notes-heading">Leave a thought for future me.</h2>
            <p className="learning-section-intro">What clicked? What is still confusing? What would I change?</p>
            <LearningNotebook />
          </section>
          <div className="learning-closing"><span>Small changes. Real understanding.</span><Link href="/docs" className="text-link">Back to the project docs <Icon name="arrow" size={15} /></Link></div>
        </div>
      </div>
    </main>
    <PageOutline headings={[
      { id: "right-now", title: "Start here" },
      { id: "build-journal", title: "Build journal" },
      { id: "small-steps", title: "The small steps" },
      { id: "concepts", title: "Concepts" },
      { id: "my-notes", title: "My own notes" },
    ]} />
    </div>
  );
}
