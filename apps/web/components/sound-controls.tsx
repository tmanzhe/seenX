"use client";

import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { schedule, SOUNDS, type SoundName } from "../lib/bencho-sounds";

const SoundContext = createContext({ enabled: true, toggle: () => {} });

const palettes = {
  click: ["wisp", "buzz", "bump", "tick", "sigh", "plop", "latch", "drift"],
  select: ["buzz", "latch", "tick", "wisp", "bump"],
  move: ["whisk", "glide", "step", "wander", "drift", "drape"],
  open: ["plop", "float", "wisp", "wander", "perk", "lull"],
  close: ["hush", "drape", "sigh", "bump", "drift"],
  search: ["wisp", "perk", "hail", "plop", "wander"],
  system: ["purr", "drone", "boot", "lull", "hush"],
} as const satisfies Record<string, readonly SoundName[]>;
type Palette = keyof typeof palettes;

// Bencho's MIT-licensed sound palette. Create audio only after an interaction.
export function SoundProvider({ children }: { children: ReactNode }) {
  const [enabled, setEnabled] = useState(true);
  const enabledRef = useRef(true);
  const context = useRef<AudioContext | null>(null);
  const lastPlayed = useRef(0);
  const lastCue = useRef<SoundName | null>(null);
  const bags = useRef<Partial<Record<Palette, SoundName[]>>>({});

  function play(choice: SoundName | Palette) {
    if (!enabledRef.current || document.hidden || performance.now() - lastPlayed.current < 65) return;
    lastPlayed.current = performance.now();
    try {
      let cue: SoundName;
      const family = choice as Palette;
      if (Object.hasOwn(palettes, family)) {
        let bag = bags.current[family];
        if (!bag?.length) {
          bag = [...palettes[family]];
          for (let i = bag.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [bag[i], bag[j]] = [bag[j], bag[i]];
          }
          bags.current[family] = bag;
        }
        // Exhaust each family before recycling, and avoid repeats across families.
        if (bag.at(-1) === lastCue.current && bag.length > 1) {
          [bag[0], bag[bag.length - 1]] = [bag[bag.length - 1], bag[0]];
        }
        cue = bag.pop()!;
        if (cue === lastCue.current) {
          const alternate = palettes[family].filter((sound) => sound !== cue);
          cue = alternate[Math.floor(Math.random() * alternate.length)];
        }
      } else cue = choice as SoundName;
      lastCue.current = cue;
      const audio = context.current ??= new AudioContext();
      if (audio.state === "suspended") void audio.resume().catch(() => {});
      const pitch = choice === "click" || choice === "select" ? 0.72 + Math.random() * 0.14 : 0.88 + Math.random() * 0.12;
      schedule(audio, SOUNDS[cue], audio.currentTime + 0.005, 0.8, pitch);
    } catch { /* Audio support must never block an interaction. */ }
  }

  useEffect(() => {
    const restore = () => {
      try { enabledRef.current = localStorage.getItem("seenx-sound") !== "off"; } catch { /* Use the session setting. */ }
      setEnabled(enabledRef.current);
    };
    restore();
    const click = (event: MouseEvent) => {
      if (!event.isTrusted || !(event.target instanceof Element)) return;
      const control = event.target.closest("button, a[href], summary");
      if (!control || control.closest("[data-sound-ignore]") || control.matches(":disabled, [aria-disabled='true']")) return;
      const explicit = control.getAttribute("data-sound");
      if (explicit && explicit in SOUNDS) play(explicit as SoundName);
      else if (control.matches(".dialog-close, [aria-label='Close search']")) return; // The dialog close event owns this cue.
      else if (control.matches(".image-card")) play("open");
      else if (control.matches(".sidebar-link")) { if (control.getAttribute("aria-pressed") !== "true") play("select"); }
      else if (control.matches("[role='tab']")) { if (control.getAttribute("aria-selected") !== "true") play("move"); }
      else if (control.matches(".theme-toggle")) play("system");
      else if (control.matches("[aria-label='Pause ASCII animation']")) play("close");
      else if (control.matches("[aria-label='Play ASCII animation']")) play("open");
      else if (control.matches(".try-queries button, .docs-search-trigger")) play("search");
      else if (control.matches("[aria-label='Clear search']")) play("close");
      else if (control.matches(".docs-mobile-toggle")) play(control.getAttribute("aria-expanded") === "true" ? "close" : "open");
      else if (control.matches("summary")) play(control.parentElement?.hasAttribute("open") ? "close" : "open");
      else if (control.matches("a[href]")) play(control.matches(".button") ? "click" : "move");
      else play("click");
    };
    const change = (event: Event) => { if (event.isTrusted && event.target instanceof HTMLSelectElement) play("select"); };
    const close = (event: Event) => { if (event.target instanceof HTMLDialogElement) play("close"); };
    const focus = (event: FocusEvent) => { if (event.target instanceof HTMLInputElement && event.target.matches(".search-field input")) play("search"); };
    document.addEventListener("click", click, true);
    document.addEventListener("change", change);
    document.addEventListener("close", close, true);
    document.addEventListener("focusin", focus);
    window.addEventListener("storage", restore);
    return () => {
      document.removeEventListener("click", click, true);
      document.removeEventListener("change", change);
      document.removeEventListener("close", close, true);
      document.removeEventListener("focusin", focus);
      window.removeEventListener("storage", restore);
      void context.current?.close().catch(() => {});
      context.current = null;
    };
  }, []);

  function toggle() {
    enabledRef.current = !enabledRef.current;
    setEnabled(enabledRef.current);
    try { localStorage.setItem("seenx-sound", enabledRef.current ? "on" : "off"); } catch { /* Keep the session setting. */ }
    if (enabledRef.current) play("system");
    else if (context.current?.state === "running") void context.current.suspend().catch(() => {});
  }

  return <SoundContext.Provider value={{ enabled, toggle }}>{children}</SoundContext.Provider>;
}

export function SoundToggle() {
  const { enabled, toggle } = useContext(SoundContext);
  return <button className="sound-toggle" data-sound-ignore onClick={toggle} aria-label="Interface sounds" aria-pressed={enabled} title={enabled ? "Mute interface sounds" : "Enable interface sounds"}>
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M11 5 6 9H3v6h3l5 4V5Z" />{enabled ? <><path d="M15 8a6 6 0 0 1 0 8" /><path d="M18 5a10 10 0 0 1 0 14" /></> : <path d="m16 9 6 6m0-6-6 6" />}</svg>
  </button>;
}
