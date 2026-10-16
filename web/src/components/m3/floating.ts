"use client";
import { useLayoutEffect, useState, type RefObject } from "react";

export interface FloatPos { top: number; left: number; width: number; maxHeight: number; above: boolean }

/** Position of a popover anchored to an element: below it (above when there is no room), kept on screen. */
export function useFloating(anchor: RefObject<HTMLElement | null>, open: boolean, opts: { gap?: number; minWidth?: number; matchWidth?: boolean; prefer?: number } = {}) {
  const { gap = 4, minWidth = 0, matchWidth = true, prefer = 320 } = opts;
  const [pos, setPos] = useState<FloatPos | null>(null);
  useLayoutEffect(() => {
    if (!open) { setPos(null); return; }
    const place = () => {
      const el = anchor.current;
      if (!el) return;
      const r = el.getBoundingClientRect(), vw = window.innerWidth, vh = window.innerHeight;
      const width = matchWidth ? Math.max(r.width, minWidth) : minWidth;
      const below = vh - r.bottom - gap - 8, aboveRoom = r.top - gap - 8;
      const above = below < Math.min(prefer, 200) && aboveRoom > below;
      const left = Math.min(Math.max(8, r.left), vw - width - 8);
      setPos({ top: above ? r.top - gap : r.bottom + gap, left, width, maxHeight: Math.max(120, above ? aboveRoom : below), above });
    };
    place();
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    return () => { window.removeEventListener("resize", place); window.removeEventListener("scroll", place, true); };
  }, [anchor, open, gap, minWidth, matchWidth, prefer]);
  return pos;
}
