"use client";

import { useEffect } from "react";

export function LandingMotion() {
  useEffect(() => {
    const root = document.querySelector<HTMLElement>(".landing-page");
    if (!root) return;
    const preference = matchMedia("(prefers-reduced-motion: reduce)");
    let dispose = () => {};

    function setup() {
      dispose();
      if (!root || preference.matches) return;
      const animations = new Set<Animation>();
      const seen = new WeakSet<Element>();
      let entrance = 0;
      const reveal = (element: Element, delay = 0) => {
        if (seen.has(element)) return;
        seen.add(element);
        // Content stays visible if JavaScript or an animation fails.
        const offsets = [[0, 8], [-7, 3], [7, 3], [0, 0], [0, -5]];
        const [x, y] = offsets[entrance++ % offsets.length];
        const animation = element.animate([
          { opacity: 0, transform: `translate(${x}px, ${y}px)` },
          { opacity: 1, transform: "translate(0, 0)" },
        ], { duration: 460, delay, easing: "cubic-bezier(.2,.7,.3,1)", fill: "backwards" });
        animations.add(animation);
        animation.onfinish = () => animations.delete(animation);
      };
      const observer = new IntersectionObserver((entries) => {
        const visible = entries.filter((entry) => entry.isIntersecting);
        visible.forEach((entry, index) => {
          reveal(entry.target, Math.min(index * 45, 135));
          observer.unobserve(entry.target);
        });
      }, { threshold: 0.08, rootMargin: "0px 0px -24px 0px" });
      root.querySelectorAll(".hero-copy > *, .demo-intro > *, .assistant-copy > *, .assistant-concept, .portability-copy > *, .portability-visual, .faq-section > div:first-child, .faq-list details").forEach((element) => observer.observe(element));

      const hero = root.querySelector<HTMLElement>(".hero-editorial");
      const scene = root.querySelector<HTMLElement>(".premium-scene-wrap");
      let pointerFrame = 0;
      let pointer = { x: 0, y: 0 };
      const applyPointer = () => {
        pointerFrame = 0;
        scene?.style.setProperty("--scene-pointer-x", String(pointer.x));
        scene?.style.setProperty("--scene-pointer-y", String(pointer.y));
      };
      const movePointer = (event: PointerEvent) => {
        if (event.pointerType !== "mouse" || !scene || !matchMedia("(hover: hover) and (pointer: fine)").matches) return;
        const bounds = scene.getBoundingClientRect();
        pointer = { x: Math.max(-1, Math.min(1, (event.clientX - bounds.left) / bounds.width * 2 - 1)), y: Math.max(-1, Math.min(1, (event.clientY - bounds.top) / bounds.height * 2 - 1)) };
        if (!pointerFrame) pointerFrame = requestAnimationFrame(applyPointer);
      };
      const resetPointer = () => { pointer = { x: 0, y: 0 }; if (!pointerFrame) pointerFrame = requestAnimationFrame(applyPointer); };
      scene?.addEventListener("pointermove", movePointer);
      scene?.addEventListener("pointerleave", resetPointer);
      let frame = 0;
      const update = () => {
        frame = 0;
        const height = document.documentElement.scrollHeight - innerHeight;
        root.style.setProperty("--page-progress", String(height > 0 ? Math.min(1, Math.max(0, scrollY / height)) : 0));
        if (hero) {
          const distance = Math.max(0, -hero.getBoundingClientRect().top);
          hero.style.setProperty("--hero-drift", `${Math.min(distance * 0.025, 12)}px`);
        }

      };
      const requestUpdate = () => { if (!frame) frame = requestAnimationFrame(update); };
      const resize = new ResizeObserver(requestUpdate);
      resize.observe(root);
      window.addEventListener("scroll", requestUpdate, { passive: true });
      window.addEventListener("resize", requestUpdate);
      root.dataset.motion = "ready";
      update();
      dispose = () => {
        observer.disconnect();
        resize.disconnect();
        animations.forEach((animation) => animation.cancel());
        cancelAnimationFrame(frame);
        cancelAnimationFrame(pointerFrame);
        scene?.removeEventListener("pointermove", movePointer);
        scene?.removeEventListener("pointerleave", resetPointer);
        scene?.style.removeProperty("--scene-pointer-x");
        scene?.style.removeProperty("--scene-pointer-y");
        window.removeEventListener("scroll", requestUpdate);
        window.removeEventListener("resize", requestUpdate);
        delete root.dataset.motion;
        root.style.removeProperty("--page-progress");
        hero?.style.removeProperty("--hero-drift");
      };
    }
    setup();
    preference.addEventListener("change", setup);
    return () => { dispose(); preference.removeEventListener("change", setup); };
  }, []);

  return <div className="scroll-progress" aria-hidden="true"><span /></div>;
}
