"use client";

import type { ReactNode } from "react";
import { usePathname } from "next/navigation";
import { Footer, Header } from "./site-chrome";

export function SiteFrame({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const isDocs = pathname === "/docs" || pathname.startsWith("/docs/") || pathname === "/learning" || pathname.startsWith("/learning/");
  if (isDocs) return children;
  return <><Header />{children}<Footer /></>;
}
