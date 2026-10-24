import Link from "next/link";

export default function NotFound() {
  return <main id="main" className="not-found section-container"><span className="eyebrow">THIS ONE GOT AWAY</span><h1>Nothing here.<br /><em>Yet.</em></h1><p>That page doesn’t exist. Let’s get you back to familiar ground.</p><Link className="button button-dark" href="/">Back to seenX →</Link></main>;
}
