"use client";

import { useEffect, useState } from "react";

export function ThemeToggle() {
  const [dark, setDark] = useState(false);
  useEffect(() => {
    const root = document.documentElement;
    let preference: string | null = null;
    try { preference = localStorage.getItem("seenx-theme"); } catch { /* System theme remains available. */ }
    const media = matchMedia("(prefers-color-scheme: dark)");
    const apply = () => { try { preference = localStorage.getItem("seenx-theme"); } catch { /* Use system preference. */ } const next = preference ? preference === "dark" : media.matches; root.dataset.theme = next ? "dark" : "light"; setDark(next); };
    apply();
    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, []);
  function toggle() {
    const next = !dark;
    document.documentElement.dataset.theme = next ? "dark" : "light";
    setDark(next);
    try { localStorage.setItem("seenx-theme", next ? "dark" : "light"); } catch { /* Keep the current session preference. */ }
  }
  return <button className="theme-toggle" onClick={toggle} aria-label={dark ? "Switch to light mode" : "Switch to dark mode"} title={dark ? "Light mode" : "Dark mode"}><span aria-hidden="true">{dark ? "☀" : "◐"}</span></button>;
}
