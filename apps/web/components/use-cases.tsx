"use client";

import Link from "next/link";
import { useState } from "react";
import { Icon } from "./icon";

const examples = {
  personal: [
    { category: "EVERYDAY WORK", title: "Get back to the useful bit.", query: "“That error I screenshotted yesterday.”", detail: "Find the message, diagram, or whiteboard you saved while you were figuring something out.", icon: "monitor" },
    { category: "CREATIVE REFERENCES", title: "Find the look you had in mind.", query: "“The black hoodie with distressed sleeves.”", detail: "Bring back an outfit, a room, or a design reference without remembering its filename.", icon: "image" },
    { category: "LITTLE ADVENTURES", title: "Remember the place, not the path.", query: "“Blue sky, green mountains, that summer trip.”", detail: "Use a description and the details you remember to return to a photo or a saved place.", icon: "pin" },
  ],
  agents: [
    { category: "CODING AGENTS", title: "Recover the missing reference.", query: "“Find the architecture diagram for this project.”", detail: "Let an agent retrieve the screenshot or diagram that gives the current task its context.", icon: "code" },
    { category: "RESEARCH AGENTS", title: "Bring the source into the answer.", query: "“Pull up the chart I saved about this.”", detail: "Return a relevant image and its visible text so the original evidence is easy to inspect.", icon: "search" },
    { category: "CREATIVE AGENTS", title: "Start from your own inspiration.", query: "“Use the room references I saved last week.”", detail: "Help a local assistant find useful visual context in the collection you already keep.", icon: "image" },
  ],
} as const;

export function UseCases() {
  const [audience, setAudience] = useState<"personal" | "agents">("personal");
  return (
    <section className="use-cases-section section-container" id="use-cases">
      <div className="section-intro"><span className="eyebrow">GOOD MEMORY. MORE POSSIBILITIES.</span><h2>Your library, put to use.</h2><p>Find it for yourself. Bring it into your next task.</p></div>
      <div className="audience-tabs" role="tablist" aria-label="Explore use cases">
        {(["personal", "agents"] as const).map((value) => <button key={value} id={`audience-${value}`} role="tab" aria-selected={audience === value} aria-controls="audience-panel" tabIndex={audience === value ? 0 : -1} onClick={() => setAudience(value)} onKeyDown={(event) => {
          if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
            event.preventDefault(); const next = event.key === "Home" ? "personal" : event.key === "End" ? "agents" : value === "personal" ? "agents" : "personal";
            setAudience(next); document.getElementById(`audience-${next}`)?.focus();
          }
        }}><Icon name={value === "personal" ? "image" : "terminal"} size={16} />{value === "personal" ? "For you" : "For your AI agents"}</button>)}
      </div>
      <div role="tabpanel" id="audience-panel" aria-labelledby={`audience-${audience}`} tabIndex={0}>
        <div className="use-case-grid">{examples[audience].map((example) => <article key={example.category}><div className="use-case-top"><span>{example.category}</span><Icon name={example.icon} size={21} /></div><h3>{example.title}</h3><blockquote>{example.query}</blockquote><p>{example.detail}</p></article>)}</div>
        <div className="use-case-bottom">{audience === "personal" && <span>Built around the things you already save.</span>}<Link href={audience === "agents" ? "/docs/agent-workflows" : "/docs/personal-search"} className="text-link">Explore the use cases <Icon name="arrow" size={15} /></Link></div>
      </div>
    </section>
  );
}
