"use client";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useId, useRef, type KeyboardEvent, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { motionTokens } from "@/lib/motion";
import { Icon } from "./Icon";

export interface DialogProps {
  open: boolean;
  /** Esc, scrim click and Cancel. */
  onClose: () => void;
  headline: ReactNode;
  /** Body copy. */
  children?: ReactNode;
  /** Right-aligned buttons; mark the safe one with data-autofocus to focus it on open. */
  actions: ReactNode;
  icon?: string;
  /** alertdialog for confirms (the mode switch, CONTRACT §4.2). */
  role?: "dialog" | "alertdialog";
}

/** M3 basic dialog (DESIGN §5.16): focus trapped, initial focus on [data-autofocus], focus restored on close. */
export function Dialog({ open, onClose, headline, children, actions, icon, role = "dialog" }: DialogProps) {
  const id = useId();
  const box = useRef<HTMLDivElement>(null);
  const back = useRef<HTMLElement | null>(null);
  useEffect(() => {
    if (!open) return;
    back.current = document.activeElement as HTMLElement;
    const t = setTimeout(() => (box.current?.querySelector<HTMLElement>("[data-autofocus]") ?? box.current?.querySelector<HTMLElement>("button"))?.focus(), 0);
    return () => { clearTimeout(t); back.current?.focus?.(); };
  }, [open]);
  const keys = (e: KeyboardEvent) => {
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); onClose(); return; }
    if (e.key !== "Tab") return;
    const f = [...(box.current?.querySelectorAll<HTMLElement>('button:not([aria-disabled="true"]), [href], input, [tabindex]:not([tabindex="-1"])') ?? [])];
    if (!f.length) return;
    const i = f.indexOf(document.activeElement as HTMLElement);
    if (e.shiftKey && i <= 0) { e.preventDefault(); f[f.length - 1].focus(); }
    else if (!e.shiftKey && i === f.length - 1) { e.preventDefault(); f[0].focus(); }
  };
  if (typeof document === "undefined") return null;
  return createPortal(
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-[70] grid place-items-center p-6" data-overlay="dialog" onKeyDown={keys}>
          <motion.div aria-hidden="true" className="absolute inset-0 bg-scrim" onClick={onClose}
            initial={{ opacity: 0 }} animate={{ opacity: 0.32 }} exit={{ opacity: 0 }} transition={motionTokens.default} />
          <motion.div ref={box} role={role} aria-modal="true" aria-labelledby={`${id}-h`} aria-describedby={children ? `${id}-b` : undefined}
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={motionTokens.default}
            className="relative w-full min-w-78 max-w-140 rounded-xl bg-surface-container-high p-6 shadow-level-3">
            {icon && <div className="mb-4 flex justify-center text-secondary"><Icon name={icon} size={24} /></div>}
            <h2 id={`${id}-h`} className={`text-headline-s text-on-surface ${icon ? "text-center" : ""}`}>{headline}</h2>
            {children && <div id={`${id}-b`} className="mt-4 text-body-m text-on-surface-variant">{children}</div>}
            <div className="mt-6 flex justify-end gap-2">{actions}</div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
