"use client";

import { useEffect, useRef } from "react";

const columns = 88;
const rows = 40;
const tones = " .,:;+=xX#@";
type Vector = [number, number, number];

function rotate([x, y, z]: Vector, yaw: number, pitch: number): Vector {
  const a = x * Math.cos(yaw) + z * Math.sin(yaw);
  const b = -x * Math.sin(yaw) + z * Math.cos(yaw);
  return [a, y * Math.cos(pitch) - b * Math.sin(pitch), y * Math.sin(pitch) + b * Math.cos(pitch)];
}

// Four spinning cubes retain the logo's grid, against the original ripple field.
function draw(time: number, pointer: { x: number; y: number }) {
  const yaw = -.2 + Math.sin(time * .45) * .18 + pointer.x * .32;
  const pitch = .16 + Math.sin(time * .35) * .12 + pointer.y * .22;
  const inverse = (v: Vector) => {
    const [x, y, z] = v;
    const b = y * Math.cos(pitch) + z * Math.sin(pitch);
    const c = -y * Math.sin(pitch) + z * Math.cos(pitch);
    return [x * Math.cos(yaw) - c * Math.sin(yaw), b, x * Math.sin(yaw) + c * Math.cos(yaw)] as Vector;
  };
  const direction = inverse([0, 0, -1]);
  const tiles = [[-6.3, -6.3], [6.3, -6.3], [-6.3, 6.3], [6.3, 6.3]];
  const spin = time * .75 + .28;
  const tumble = Math.sin(time * .6) * .35;
  const unspin = ([x, y, z]: Vector): Vector => {
    const b = y * Math.cos(tumble) + z * Math.sin(tumble);
    const c = -y * Math.sin(tumble) + z * Math.cos(tumble);
    return [x * Math.cos(spin) - c * Math.sin(spin), b, x * Math.sin(spin) + c * Math.cos(spin)];
  };
  const half = [4.15, 4.15, 4.15];
  return Array.from({ length: rows }, (_, y) => Array.from({ length: columns }, (_, x) => {
    const px = (x - columns / 2) / 2, py = y - rows / 2;
    const origin = inverse([px, py, 50]);
    let nearest = Infinity;
    const radius = Math.hypot(px, py);
    const wave = Math.sin(radius * .68 - time * 2.4) * .5 + .5;
    let brightness = wave * Math.max(0, 1 - radius / 32) * .3;
    for (let tile = 0; tile < tiles.length; tile++) {
      const [cx, cy] = tiles[tile];
      const angle = tile === 3 ? Math.PI / 12 : 0;
      const cos = Math.cos(angle), sin = Math.sin(angle);
      const ox = origin[0] - cx, oy = origin[1] - cy;
      const local = unspin([ox * cos + oy * sin, -ox * sin + oy * cos, origin[2]]);
      const ray = unspin([direction[0] * cos + direction[1] * sin, -direction[0] * sin + direction[1] * cos, direction[2]]);
      let near = -Infinity, far = Infinity, face = 0, sign = 1;
      for (let axis = 0; axis < 3; axis++) {
        if (Math.abs(ray[axis]) < 1e-8) {
          if (Math.abs(local[axis]) > half[axis]) { far = -Infinity; break; }
          continue;
        }
        const a = (-half[axis] - local[axis]) / ray[axis];
        const b = (half[axis] - local[axis]) / ray[axis];
        const entry = Math.min(a, b);
        if (entry > near) { near = entry; face = axis; sign = a < b ? -1 : 1; }
        far = Math.min(far, Math.max(a, b));
      }
      if (near > far || near < 0 || near >= nearest) continue;
      nearest = near;
      const normal: Vector = [0, 0, 0];
      normal[face] = sign;
      const spun = rotate(normal, spin, tumble);
      const world = rotate([spun[0] * cos - spun[1] * sin, spun[0] * sin + spun[1] * cos, spun[2]], yaw, pitch);
      const light = Math.max(0, -world[0] * .35 - world[1] * .45 + world[2] * .82);
      brightness = Math.min(1, .28 + light * .7);
    }
    return tones[Math.floor(brightness * (tones.length - 1))];
  }).join("")).join("\n");
}

export function AsciiMemory() {
  const host = useRef<HTMLDivElement>(null);
  const output = useRef<HTMLPreElement>(null);
  const pointer = useRef({ x: 0, y: 0 });
  useEffect(() => {
    const media = matchMedia("(prefers-reduced-motion: reduce)");
    let visible = false;
    let animation = 0;
    let previous = 0;
    let elapsed = 0;
    const eased = { x: 0, y: 0 };
    const tick = (now: number) => {
      if (now - previous >= 32) {
        elapsed += previous ? Math.min((now - previous) / 1000, .1) : 0;
        previous = now;
        eased.x += (pointer.current.x - eased.x) * .15;
        eased.y += (pointer.current.y - eased.y) * .15;
        if (output.current) output.current.textContent = draw(elapsed, eased);
      }
      animation = requestAnimationFrame(tick);
    };
    const update = () => {
      cancelAnimationFrame(animation);
      previous = 0;
      if (visible && !media.matches && !document.hidden) animation = requestAnimationFrame(tick);
      else if (media.matches && output.current) output.current.textContent = draw(0, { x: 0, y: 0 });
    };
    const observer = new IntersectionObserver(entries => { visible = entries[0].isIntersecting; update(); });
    if (host.current) observer.observe(host.current);
    media.addEventListener("change", update);
    document.addEventListener("visibilitychange", update);
    const hero = host.current?.closest(".hero-editorial");
    const move = (event: Event) => {
      if (media.matches || !(event instanceof PointerEvent) || event.pointerType !== "mouse" || !hero) return;
      const bounds = hero.getBoundingClientRect();
      pointer.current = { x: (event.clientX - bounds.left) / bounds.width * 2 - 1, y: (event.clientY - bounds.top) / bounds.height * 2 - 1 };
    };
    const reset = () => { pointer.current = { x: 0, y: 0 }; };
    hero?.addEventListener("pointermove", move);
    hero?.addEventListener("pointerleave", reset);
    return () => { cancelAnimationFrame(animation); observer.disconnect(); media.removeEventListener("change", update); document.removeEventListener("visibilitychange", update); hero?.removeEventListener("pointermove", move); hero?.removeEventListener("pointerleave", reset); };
  }, []);
  return <div className="ascii-memory" ref={host}>
    <pre ref={output} aria-hidden="true">{draw(0, { x: 0, y: 0 })}</pre>
  </div>;
}
