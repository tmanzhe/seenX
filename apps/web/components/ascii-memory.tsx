"use client";

import { useEffect, useRef } from "react";

const columns = 144;
const rows = 56;
const tones = " .,:;=+xX#@";
type Vector = [number, number, number];
type Pointer = { x: number; y: number };

function rotate([x, y, z]: Vector, yaw: number, pitch: number): Vector {
  const a = x * Math.cos(yaw) + z * Math.sin(yaw);
  const b = -x * Math.sin(yaw) + z * Math.cos(yaw);
  return [a, y * Math.cos(pitch) - b * Math.sin(pitch), y * Math.sin(pitch) + b * Math.cos(pitch)];
}

// Sample actual cube faces once; each frame projects them into a character grid.
const surface: { point: Vector; normal: Vector; edge: boolean }[] = [];
for (let axis = 0; axis < 3; axis++) {
  for (const side of [-1, 1]) {
    for (let u = 0; u <= 18; u++) for (let v = 0; v <= 18; v++) {
      const point: Vector = [0, 0, 0], normal: Vector = [0, 0, 0];
      point[axis] = side * 3.35; normal[axis] = side;
      point[(axis + 1) % 3] = (u / 18 * 2 - 1) * 3.35;
      point[(axis + 2) % 3] = (v / 18 * 2 - 1) * 3.35;
      surface.push({ point, normal, edge: u === 0 || u === 18 || v === 0 || v === 18 });
    }
  }
}

function draw(time: number, pointer: Pointer, scroll = 0) {
  const field: string[] = [], solid = Array<string>(columns * rows).fill(" ");
  const depth = new Float32Array(columns * rows).fill(-Infinity);
  const phase = time * .65 + scroll * 3;
  // A travelling contour field, broken isometric grid, and quiet data points.
  for (let y = 0; y < rows; y++) for (let x = 0; x < columns; x++) {
    const px = (x - columns / 2) * .55, py = (y - rows / 2) * .95;
    const contour = Math.sin(Math.hypot(px + 19, py * .8) * .72 - phase + Math.sin(px * .1 + phase * .3));
    const gridA = Math.abs(((px + py * 1.5 + scroll * 5) % 12 + 12) % 12 - 6);
    const gridB = Math.abs(((px - py * 1.5 - scroll * 5) % 12 + 12) % 12 - 6);
    const hash = (x * 17 + y * 31) % 97;
    let glyph = " ";
    if (contour > .94) glyph = contour > .99 ? ":" : ".";
    if ((gridA < .23 || gridB < .23) && hash % 3 === 0) glyph = "·";
    if (hash === 0) glyph = Math.sin(phase + x * .2) > .65 ? "+" : ".";
    if ((x + y * 7) % 173 === 0) glyph = "×";
    field.push(glyph);
  }
  const yaw = -.3 + pointer.x * .2 + scroll * .2;
  const pitch = -.12 + pointer.y * .16;
  const spin = time * .48 + .45 + scroll * .85;
  const tumble = Math.sin(time * .32) * .28 + .15;
  const tiles = [[-5, -5], [5, -5], [-5, 5], [5, 5]];
  tiles.forEach(([cx, cy], tile) => {
    const angle = tile === 3 ? Math.PI / 12 : 0;
    const cos = Math.cos(angle), sin = Math.sin(angle);
    for (const sample of surface) {
      const spun = rotate(sample.point, spin, tumble);
      const local: Vector = [spun[0] * cos - spun[1] * sin + cx, spun[0] * sin + spun[1] * cos + cy, spun[2]];
      const [rx, ry, rz] = rotate(local, yaw, pitch);
      const normal = rotate(sample.normal, spin, tumble);
      const facing = rotate([normal[0] * cos - normal[1] * sin, normal[0] * sin + normal[1] * cos, normal[2]], yaw, pitch);
      if (facing[2] <= 0) continue;
      const perspective = 65 / (65 - rz);
      const x = Math.round((rx * perspective + 26 + pointer.x * .7) / .55 + columns / 2);
      const y = Math.round((ry * perspective - 1 + Math.sin(time * .5) * .6) / .95 + rows / 2);
      if (x < 0 || x >= columns || y < 0 || y >= rows) continue;
      const index = y * columns + x;
      if (rz < depth[index]) continue;
      depth[index] = rz;
      const light = Math.max(0, -facing[0] * .4 - facing[1] * .5 + facing[2] * .75);
      solid[index] = sample.edge ? "+" : tones[Math.min(tones.length - 1, Math.floor((.22 + light * .75) * (tones.length - 1)))];
    }
  });
  const lines = (grid: string[]) => Array.from({ length: rows }, (_, y) => grid.slice(y * columns, (y + 1) * columns).join("")).join("\n");
  return { field: lines(field), solid: lines(solid) };
}

const initial = draw(0, { x: 0, y: 0 });

export function AsciiMemory() {
  const host = useRef<HTMLDivElement>(null);
  const field = useRef<HTMLPreElement>(null);
  const solid = useRef<HTMLPreElement>(null);
  useEffect(() => {
    const element = host.current;
    if (!element) return;
    const media = matchMedia("(prefers-reduced-motion: reduce)");
    let visible = false, animation = 0, previous = 0, elapsed = 0;
    let targetScroll = 0, scroll = 0;
    const pointer = { x: 0, y: 0 }, eased = { x: 0, y: 0 };
    const render = () => {
      const frame = draw(elapsed, eased, scroll);
      if (field.current) field.current.textContent = frame.field;
      if (solid.current) solid.current.textContent = frame.solid;
    };
    const tick = (now: number) => {
      if (now - previous >= 32) {
        elapsed += previous ? Math.min((now - previous) / 1000, .1) : 0;
        previous = now;
        eased.x += (pointer.x - eased.x) * .12;
        eased.y += (pointer.y - eased.y) * .12;
        scroll += (targetScroll - scroll) * .16;
        render();
      }
      animation = requestAnimationFrame(tick);
    };
    const update = () => {
      cancelAnimationFrame(animation); previous = 0;
      if (visible && !media.matches && !document.hidden) animation = requestAnimationFrame(tick);
      else if (media.matches) {
        elapsed = 0; scroll = 0; eased.x = 0; eased.y = 0; render();
      }
    };
    const observer = new IntersectionObserver(entries => { visible = entries[0].isIntersecting; update(); });
    observer.observe(element);
    const hero = element.closest(".hero-editorial");
    const move = (event: Event) => {
      if (media.matches || !(event instanceof PointerEvent) || event.pointerType !== "mouse" || !hero) return;
      const bounds = hero.getBoundingClientRect();
      pointer.x = Math.max(-1, Math.min(1, (event.clientX - bounds.left) / bounds.width * 2 - 1));
      pointer.y = Math.max(-1, Math.min(1, event.clientY / innerHeight * 2 - 1));
    };
    const reset = () => { pointer.x = 0; pointer.y = 0; };
    const onScroll = () => { targetScroll = Math.min(1, Math.max(0, -element.getBoundingClientRect().top / Math.max(1, element.clientHeight))); };
    onScroll();
    media.addEventListener("change", update);
    document.addEventListener("visibilitychange", update);
    window.addEventListener("scroll", onScroll, { passive: true });
    hero?.addEventListener("pointermove", move);
    hero?.addEventListener("pointerleave", reset);
    return () => {
      cancelAnimationFrame(animation); observer.disconnect();
      media.removeEventListener("change", update);
      document.removeEventListener("visibilitychange", update);
      window.removeEventListener("scroll", onScroll);
      hero?.removeEventListener("pointermove", move);
      hero?.removeEventListener("pointerleave", reset);
    };
  }, []);
  return <div className="ascii-memory" ref={host} aria-hidden="true">
    <pre className="ascii-field" ref={field}>{initial.field}</pre>
    <pre className="ascii-form" ref={solid}>{initial.solid}</pre>
  </div>;
}
