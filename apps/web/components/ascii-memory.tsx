"use client";

import { useEffect, useRef, useState } from "react";

const columns = 80;
const rows = 34;
const tones = " .,:;+=xX#@";

function draw(frame: number) {
  return Array.from({ length: rows }, (_, y) => Array.from({ length: columns }, (_, x) => {
    const px = (x - 40) / 2;
    const py = y - 17;
    const radius = Math.hypot(px, py);
    const wave = Math.sin(radius * .68 - frame * .17) * .5 + .5;
    const square = Math.abs(px) > 2 && Math.abs(px) < 12 && Math.abs(py) > 2 && Math.abs(py) < 12;
    const edge = Math.abs(px) < 13 && Math.abs(py) < 13;
    const brightness = square ? .58 + wave * .4 : edge ? wave * .16 : wave * Math.max(0, 1 - radius / 30) * .28;
    return tones[Math.floor(brightness * (tones.length - 1))];
  }).join("")).join("\n");
}

export function AsciiMemory() {
  const [frame, setFrame] = useState(0);
  const [paused, setPaused] = useState(false);
  const host = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const media = matchMedia("(prefers-reduced-motion: reduce)");
    let visible = false;
    let timer: ReturnType<typeof setInterval> | undefined;
    const update = () => {
      clearInterval(timer);
      if (visible && !paused && !media.matches && !document.hidden) timer = setInterval(() => setFrame(value => (value + 1) % 10000), 140);
    };
    const observer = new IntersectionObserver(entries => { visible = entries[0].isIntersecting; update(); });
    if (host.current) observer.observe(host.current);
    media.addEventListener("change", update);
    document.addEventListener("visibilitychange", update);
    return () => { clearInterval(timer); observer.disconnect(); media.removeEventListener("change", update); document.removeEventListener("visibilitychange", update); };
  }, [paused]);
  return <div className="ascii-memory" ref={host}>
    <div className="ascii-coordinate ascii-coordinate-top" aria-hidden="true">[ LOCAL MEMORY FIELD ]<span>01 — 04</span></div>
    <pre aria-hidden="true">{draw(frame)}</pre>
    <div className="ascii-coordinate ascii-coordinate-bottom"><span aria-hidden="true">WORDS / PIXELS / CONNECTIONS</span><button onClick={() => setPaused(!paused)} aria-label={paused ? "Play ASCII animation" : "Pause ASCII animation"}>{paused ? "[ play ]" : "[ pause ]"}</button></div>
  </div>;
}
