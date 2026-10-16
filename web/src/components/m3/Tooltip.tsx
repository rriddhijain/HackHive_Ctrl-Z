"use client";
import { cloneElement, isValidElement, useEffect, useId, useLayoutEffect, useRef, useState, type ReactElement, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "motion/react";
import { motionTokens } from "@/lib/motion";

export interface TooltipProps {
  /** Plain tooltip text (verbatim CONTRACT copy). */
  content?: ReactNode;
  /** Rich tooltip: optional subhead over the supporting text (status cluster, System grid). */
  rich?: { subhead?: ReactNode; body: ReactNode };
  /** One element; it gets aria-describedby. */
  children: ReactElement;
  /** Layout of the wrapper (it is an inline-flex span). */
  className?: string;
  /** Hover delay before showing (focus shows at once). */
  delay?: number;
}

/** M3 plain / rich tooltip (DESIGN §5.15): 500 ms hover or keyboard focus; Esc or leave hides it. */
export function Tooltip({ content, rich, children, className = "", delay = 500 }: TooltipProps) {
  const id = useId();
  const wrap = useRef<HTMLSpanElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ x: number; y: number; above: boolean } | null>(null);
  const show = (now: boolean) => { clearTimeout(timer.current); timer.current = setTimeout(() => setOpen(true), now ? 0 : delay); };
  const hide = () => { clearTimeout(timer.current); setOpen(false); };
  useEffect(() => () => clearTimeout(timer.current), []);
  useEffect(() => {
    if (!open) return;
    const k = (e: KeyboardEvent) => { if (e.key === "Escape") hide(); };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [open]);
  useLayoutEffect(() => {
    if (!open || !wrap.current) return;
    const r = wrap.current.getBoundingClientRect();
    const above = r.bottom + 80 > window.innerHeight;
    setPos({ x: r.left + r.width / 2, y: above ? r.top - 8 : r.bottom + 8, above });
  }, [open]);
  if (!content && !rich) return children;
  const child = isValidElement(children) ? cloneElement(children as ReactElement<{ "aria-describedby"?: string }>, { "aria-describedby": open ? id : undefined }) : children;
  return (
    <span ref={wrap} className={`inline-flex ${className}`} onMouseEnter={() => show(false)} onMouseLeave={hide}
      onFocus={(e) => { if ((e.target as HTMLElement).matches(":focus-visible")) show(true); }} onBlur={hide} onPointerDown={hide}>
      {child}
      {typeof document !== "undefined" && createPortal(
        <AnimatePresence>
          {open && pos && (
            <motion.div id={id} role="tooltip" data-overlay="tooltip"
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={motionTokens.fast}
              style={{ position: "fixed", left: pos.x, top: pos.y, x: "-50%", y: pos.above ? "-100%" : 0 }}
              className={`pointer-events-none z-[60] ${rich
                ? "w-max max-w-80 rounded-md bg-surface-container-high px-4 py-3 text-on-surface-variant shadow-level-2"
                : "w-max max-w-60 rounded-xs bg-inverse-surface px-2 py-1 text-body-s text-inverse-on-surface"}`}>
              {rich ? (
                <>
                  {rich.subhead && <div className="mb-1 text-title-s text-on-surface">{rich.subhead}</div>}
                  <div className="text-body-m">{rich.body}</div>
                </>
              ) : content}
            </motion.div>
          )}
        </AnimatePresence>,
        document.body,
      )}
    </span>
  );
}
