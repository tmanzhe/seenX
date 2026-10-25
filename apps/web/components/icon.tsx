import type { CSSProperties } from "react";

const paths = {
  arrow: "M5 12h14m-6-6 6 6-6 6",
  diagonal: "M6 18 18 6M6 6h12v12",
  search: "m20 20-5-5M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0Z",
  folder: "M3 7V5h6l2 2h10v12H3V7Z",
  image: "M3 3h18v18H3V3Zm0 14 6-6 4 4 3-3 5 5M16 7h.01",
  lock: "M5 10h14v11H5V10Zm3 0V7a4 4 0 0 1 8 0v3m-4 4v3",
  pin: "M12 22s8-7 8-13a8 8 0 1 0-16 0c0 6 8 13 8 13Zm3-13a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z",
  code: "m8 6-6 6 6 6m8-12 6 6-6 6m-3-15-2 18",
  heart: "M20.8 4.6a5.5 5.5 0 0 0-7.8 0l-1 1-1-1a5.5 5.5 0 0 0-7.8 7.8L12 22l8.8-9.6a5.5 5.5 0 0 0 0-7.8Z",
  check: "m5 12 4 4L19 6",
  close: "m6 6 12 12M6 18 18 6",
  terminal: "m4 6 6 6-6 6m9 0h7",
  menu: "M4 7h16M4 12h16M4 17h16",
  monitor: "M3 3h18v14H3V3Zm5 18h8m-4-4v4",
  region: "M8 3H3v5m13-5h5v5M3 16v5h5m8 0h5v-5M8 8h8v8H8Z",
  plus: "M12 5v14M5 12h14",
};

export function Icon({ name, size = 20, style }: { name: keyof typeof paths; size?: number; style?: CSSProperties }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={style}><path d={paths[name]} /></svg>;
}
