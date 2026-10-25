import Link from "next/link";
import { Icon } from "./icon";
import { ThemeToggle } from "./theme-toggle";
import { SoundToggle } from "./sound-controls";

export function Brand() {
  return <Link href="/" className="brand" aria-label="seenX home"><span className="brand-symbol" aria-hidden="true"><i /><i /><i /><i /></span><span>seen<span className="brand-x">X</span></span></Link>;
}

export function Header() {
  return (
    <header className="site-header">
      <div className="nav-inner">
        <Brand />
        <nav aria-label="Main navigation">
          <Link href="/#use-cases" className="nav-product">Use cases</Link>
          <Link href="/docs">Docs</Link>
          <Link href="/support" className="nav-support">Support <Icon name="heart" size={14} /></Link>
        </nav>
        <ThemeToggle /><SoundToggle /><Link href="/#demo" className="button button-small button-dark">Try the preview <Icon name="diagonal" size={15} /></Link>
      </div>
    </header>
  );
}

export function Footer() {
  return (
    <footer className="site-footer">
      <div className="footer-top"><div><Brand /><p>Find what you remember.</p></div><div className="footer-links"><Link href="/docs">Documentation</Link><Link href="/support">Support the project</Link></div></div>
      <div className="footer-bottom"><span>© {new Date().getUTCFullYear()} seenX</span><span><span className="status-dot" /> In development · macOS first</span></div>
    </footer>
  );
}
