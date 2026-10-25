import { Icon } from "./icon";

const examples = [
  { category: "THE INSPIRATION", title: "More than a pretty picture.", note: "Love the navigation. Not the colors.", query: "Find the checkout flow I wanted to soften.", icon: "image" },
  { category: "THE EVERYDAY", title: "The little details, kept close.", note: "Try the matcha when we’re back in Kyoto.", query: "Which café did I want to go back to?", icon: "pin" },
  { category: "THE THING THAT WORKED", title: "A way back to the answer.", note: "Starting the database fixed this one.", query: "What fixed that connection error?", icon: "terminal" },
] as const;

export function UseCases() {
  return <section className="use-cases-section section-container" id="use-cases"><div className="section-intro"><span className="eyebrow">FOR ALL THE THINGS YOU KEEP</span><h2>Only you know why you saved it.</h2><p>Your notes give the image a meaning that a model can’t infer.</p></div><div className="use-case-grid">{examples.map((example) => <article key={example.category}><div className="use-case-top"><span>{example.category}</span><Icon name={example.icon} size={20} /></div><h3>{example.title}</h3><blockquote>“{example.note}”</blockquote><p>{example.query}</p></article>)}</div></section>;
}
