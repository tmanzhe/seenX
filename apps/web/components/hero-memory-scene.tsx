"use client";

import { useEffect, useRef, useState, type CSSProperties } from "react";
import { demoItems } from "../lib/demo";
import { Icon } from "./icon";
import { MemoryArtwork } from "./memory-artwork";
import styles from "./hero-memory-scene.module.css";

const orbitPaths = [
  "M 950 320 C 950 475 748 600 500 600 C 252 600 50 475 50 320 C 50 165 252 40 500 40 C 748 40 950 165 950 320",
  "M 925 320 C 925 450 735 555 500 555 C 265 555 75 450 75 320 C 75 190 265 85 500 85 C 735 85 925 190 925 320",
  "M 970 320 C 970 495 760 620 500 620 C 240 620 30 495 30 320 C 30 145 240 20 500 20 C 760 20 970 145 970 320",
];

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
    const orbit = root.querySelector<SVGPathElement>("[data-orbit-path]");
    const head = root.querySelector<SVGGElement>("[data-orbit-head]");
    const length = orbit?.getTotalLength() ?? 0;
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
      root.style.setProperty("--orbit-rotation", `${-16 + progress * 22}deg`);
      if (orbit && head) {
        const point = orbit.getPointAtLength(length * progress);
        head.setAttribute("transform", `translate(${point.x} ${point.y})`);
      }
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
        <div className={styles.stage} data-memory-stage role="group" aria-label={steps[step].name + " walkthrough scene"}>
          <div className={styles.halo} aria-hidden="true" />
          <svg className={styles.orbit} viewBox="0 0 1000 640" aria-hidden="true" focusable="false">
            {orbitPaths.map((path, index) => <g key={path}>
              <path className={styles.orbitGuide} d={path} />
              <path className={styles.orbitInk} d={path} pathLength="1" data-orbit-path={index === 0 ? "" : undefined} style={{ "--trail-delay": index * .12 } as CSSProperties} />
            </g>)}
            <g className={styles.orbitHead} data-orbit-head transform="translate(950 320)"><circle r="12" /><circle r="4" /></g>
          </svg>

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
