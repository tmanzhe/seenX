"use client";

import { useId, useRef, useState, type KeyboardEvent } from "react";
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
  const [step, setStep] = useState(1);
  const id = useId();
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);

  function navigateTabs(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    let next = index;
    if (event.key === "ArrowRight") next = (index + 1) % steps.length;
    else if (event.key === "ArrowLeft") next = (index + steps.length - 1) % steps.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = steps.length - 1;
    else return;
    event.preventDefault();
    setStep(next);
    tabRefs.current[next]?.focus();
  }

  return <div className={styles.scene} data-step={step}>
    <div className={styles.stage} id={`${id}-panel`} role="tabpanel" aria-labelledby={`${id}-tab-${step}`}>
      <div className={styles.halo} aria-hidden="true" />
      <div className={styles.orbit} aria-hidden="true" />
      <div className={styles.previewLabel}><span /> Interactive preview</div>

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
        <button type="button" tabIndex={step === 0 ? 0 : -1} onClick={() => setStep(1)} aria-label="Preview adding a note"><Icon name="plus" size={17} /></button>
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

    <div className={styles.controls}>
      <div className={styles.tabs} role="tablist" aria-label="Explore the SeenX workflow">
        {steps.map((item, index) => <button key={item.name} ref={(node) => { tabRefs.current[index] = node; }} id={`${id}-tab-${index}`} type="button" role="tab" aria-selected={step === index} aria-controls={`${id}-panel`} tabIndex={step === index ? 0 : -1} onClick={() => setStep(index)} onKeyDown={(event) => navigateTabs(event, index)}><Icon name={item.icon} size={15} /><span>{item.name}</span></button>)}
      </div>
      <p className="sr-only" aria-live="polite">{steps[step].description}</p>
    </div>
  </div>;
}
