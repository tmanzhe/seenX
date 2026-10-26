"use client";

import { useEffect, useRef, useState } from "react";
import { demoItems } from "../lib/demo";
import { Icon } from "./icon";
import { MemoryArtwork } from "./memory-artwork";
import styles from "./hero-memory-scene.module.css";

const steps = [
  { name: "Capture", description: "A little inspiration. Worth keeping.", icon: "monitor" },
  { name: "Annotate", description: "Keep the detail. Add your point of view.", icon: "region" },
  { name: "Recall", description: "Find the image. Remember exactly why.", icon: "search" },
] as const;

export function HeroMemoryScene() {
  const [step, setStep] = useState(0);
  const [staticView, setStaticView] = useState(false);
  const host = useRef<HTMLDivElement>(null);
  const sticky = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const root = host.current;
    const frame = sticky.current;
    if (!root || !frame) return;
    const media = matchMedia("(prefers-reduced-motion: reduce)");
    let raf = 0;
    let previousStep = -1;
    const update = () => {
      raf = 0;
      const reduced = media.matches;
      const inset = parseFloat(getComputedStyle(frame).top) || 0;
      const distance = Math.max(1, root.offsetHeight - frame.offsetHeight);
      const progress = reduced ? 1 : Math.min(1, Math.max(0, (inset - root.getBoundingClientRect().top) / distance));
      root.style.setProperty("--story-progress", String(progress));
      const next = reduced ? 1 : progress < .28 ? 0 : progress < .68 ? 1 : 2;
      if (next !== previousStep) { previousStep = next; setStep(next); }
    };
    const schedule = () => { if (!raf) raf = requestAnimationFrame(update); };
    const preferenceChanged = () => { setStaticView(media.matches); schedule(); };
    const resize = new ResizeObserver(schedule);
    resize.observe(root); resize.observe(frame);
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    media.addEventListener("change", preferenceChanged);
    setStaticView(media.matches);
    update();
    return () => {
      cancelAnimationFrame(raf); resize.disconnect();
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
      media.removeEventListener("change", preferenceChanged);
    };
  }, []);

  return <div ref={host} id="how-it-works" className={styles.scrollStory} data-walkthrough data-step={step} data-static={staticView}>
    <div ref={sticky} className={styles.stickyScene}>
      <div className={styles.scene} data-step={step}>
        <div className={styles.storyHeader}><span>{staticView ? "How seenX works" : "Scroll to watch"}<Icon name="arrow" size={12} /></span><a href="#demo">Skip to the hands-on demo <Icon name="diagonal" size={12} /></a></div>
        <div className={styles.stage} data-memory-stage role="group" aria-label={steps[step].name + " walkthrough scene"}>
          <div className={styles.halo} aria-hidden="true" />
          <div className={styles.orbit} aria-hidden="true" />

          <div className={styles.browser}>
            <div className={styles.browserBar}>
              <div className={styles.windowDots} aria-hidden="true"><i /><i /><i /></div>
              <span><Icon name="lock" size={10} /> example.com/shop</span>
              <Icon name="plus" size={13} />
            </div>
            <div className={styles.screenshot}>
              <MemoryArtwork item={demoItems[0]} />
              <div className={styles.captureCorners} aria-hidden="true"><i /><i /><i /><i /></div>
              <div className={styles.highlight} aria-hidden="true"><span>1</span><i /><i /><i /><i /></div>
              <div className={styles.cursor} aria-hidden="true"><svg viewBox="0 0 24 28"><path d="m3 2 17 15-9 1-5 7Z" /></svg><span>You</span></div>
            </div>
          </div>

          <div className={styles.capturePill} aria-hidden={step !== 0}>
            <span className={styles.captureIcon}><Icon name="monitor" size={19} /></span>
            <span><strong>A moment, captured.</strong><small>Add a thought before it slips away.</small></span>
            <span className={styles.capturePlus} aria-hidden="true"><Icon name="plus" size={17} /></span>
          </div>

          <div className={styles.noteCard} aria-hidden={step === 0}>
            <div className={styles.noteHeading}><span className={styles.noteIcon}><Icon name="pin" size={15} /></span><span>Your point of view</span><span className={styles.noteNumber}>01</span></div>
            <div className={styles.quote}><span /> Continue to checkout</div>
            <p>Love the generous spacing.<br />Try a softer blue for this button.</p>
            <div className={styles.noteFoot}><span><Icon name="region" size={11} /> Attached to this detail</span><Icon name="check" size={13} /></div>
          </div>

          <div className={styles.searchCard} aria-hidden={step !== 2}>
            <div className={styles.searchField}><Icon name="search" size={19} /><span>the checkout with the softer blue</span><kbd>⌘ K</kbd></div>
            <div className={styles.searchResult}>
              <div className={styles.resultImage}><MemoryArtwork item={demoItems[0]} /></div>
              <div><strong>That checkout you saved.</strong><span>“Try a softer blue for this button.”</span><small><Icon name="pin" size={10} /> Found in your note</small></div>
              <span className={styles.resultArrow}><Icon name="arrow" size={16} /></span>
            </div>
          </div>

        </div>

        <div className={styles.progressTrack} aria-hidden="true"><span /></div>
        <ol className={styles.progressSteps} aria-label="Capture, annotate, and recall walkthrough">
          {steps.map((item, index) => <li key={item.name} data-active={step === index} data-complete={step > index} aria-current={!staticView && step === index ? "step" : undefined}><span className={styles.progressName}><Icon name={item.icon} size={14} />{item.name}</span><p>{item.description}</p></li>)}
        </ol>
        <p className={styles.scrollCue} aria-hidden="true">{step === 2 ? "Next: try it yourself below" : "Keep scrolling"}<Icon name="arrow" size={12} /></p>
        <p className="sr-only" aria-live="polite">{steps[step].name}: {steps[step].description}</p>
      </div>
    </div>
  </div>;
}
