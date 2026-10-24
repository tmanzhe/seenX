import type { Metadata } from "next";
import Link from "next/link";
import { Icon } from "../../components/icon";

export const metadata: Metadata = { title: "Support the project" };

export default function Support() {
  return <main id="main" className="support-page section-container"><span className="support-heart"><Icon name="heart" size={29} /></span><span className="eyebrow">GOOD TOOLS GROW WITH GOOD PEOPLE</span><h1>Small project.<br /><em>Shared possibility.</em></h1><p className="support-description">The plan is simple: make seenX free and open source.<br />Let people support it if they find it useful.</p><div className="support-notice"><span className="status-dot" /><div><strong>We’re still getting started.</strong><p>Optional donations will come later. For now, explore the project and follow the build.</p></div></div><div className="support-options"><article><span className="step-number">01 / UNDERSTAND IT</span><h2>Take a look around.</h2><p>Explore the sample library and the design decisions behind the app.</p><Link className="text-link" href="/#demo">Try the preview <Icon name="arrow" size={16} /></Link></article><article><span className="step-number">02 / FOLLOW ALONG</span><h2>See what’s next.</h2><p>See what we’re working on and where the project is headed.</p><Link className="text-link" href="/docs/roadmap">Read the roadmap <Icon name="arrow" size={16} /></Link></article><article><span className="step-number">03 / WHEN IT’S READY</span><h2>Contribute your way.</h2><p>Bug reports, documentation, evaluation examples, and optional donations can help once the project is public.</p><Link className="text-link" href="/docs/open-source">Read the release approach <Icon name="arrow" size={16} /></Link></article></div></main>;
}
