"use client";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, type KeyboardEvent, type ReactNode, type RefObject } from "react";
import { createPortal } from "react-dom";
import { motionTokens } from "@/lib/motion";
import { useFloating } from "./floating";
import { Icon } from "./Icon";

export interface MenuProps {
  open: boolean;
  onClose: () => void;
  /** The element the menu hangs from (its width is the menu's minimum width). */
  anchor: RefObject<HTMLElement | null>;
  children: ReactNode;
  /** "menu" (standalone; arrow keys move focus) or "listbox" (driven by Select via aria-activedescendant). */
  role?: "menu" | "listbox";
  id?: string;
  "aria-label"?: string;
  "aria-activedescendant"?: string;
  minWidth?: number;
  onKeyDown?: (e: KeyboardEvent<HTMLDivElement>) => void;
}

/**
 * M3 menu (DESIGN §5.7): one opaque surface-container-low surface, elevation 2, groups split by a divider.
 * Portalled, flips above when there is no room, closes on outside press, Esc and Tab. Fades open (basic motion).
 */
export function Menu({ open, onClose, anchor, children, role = "menu", id, minWidth = 280, onKeyDown, ...aria }: MenuProps) {
  const pos = useFloating(anchor, open, { minWidth });
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const down = (e: PointerEvent) => {
      const t = e.target as Node;
      if (!box.current?.contains(t) && !anchor.current?.contains(t)) onClose();
    };
    document.addEventListener("pointerdown", down, true);
    return () => document.removeEventListener("pointerdown", down, true);
  }, [open, onClose, anchor]);
  useEffect(() => {   // standalone menus take focus
    if (open && role === "menu" && pos) box.current?.querySelector<HTMLElement>('[role="menuitem"]:not([aria-disabled="true"])')?.focus();
  }, [open, role, pos]);
  const keys = (e: KeyboardEvent<HTMLDivElement>) => {
    onKeyDown?.(e);
    if (e.defaultPrevented) return;
    if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); onClose(); anchor.current?.focus(); return; }
    if (e.key === "Tab") { onClose(); return; }
    if (role !== "menu") return;
    const items = [...(box.current?.querySelectorAll<HTMLElement>('[role="menuitem"]:not([aria-disabled="true"])') ?? [])];
    const i = items.indexOf(document.activeElement as HTMLElement);
    const to = e.key === "ArrowDown" ? (i + 1) % items.length : e.key === "ArrowUp" ? (i - 1 + items.length) % items.length
      : e.key === "Home" ? 0 : e.key === "End" ? items.length - 1 : -1;
    if (to >= 0) { e.preventDefault(); items[to]?.focus(); }
  };
  if (typeof document === "undefined") return null;
  return createPortal(
    <AnimatePresence>
      {open && pos && (
        <motion.div ref={box} id={id} role={role} aria-label={aria["aria-label"]} aria-activedescendant={aria["aria-activedescendant"]}
          tabIndex={-1} onKeyDown={keys} data-overlay="menu"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={motionTokens.fast}
          style={{ position: "fixed", left: pos.left, top: pos.top, width: pos.width, maxHeight: Math.min(pos.maxHeight, 520), y: pos.above ? "-100%" : 0 }}
          className="z-50 flex flex-col overflow-y-auto overscroll-contain rounded-lg bg-surface-container-low py-1 shadow-level-2 outline-none">
          {children}
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}

/** A group of menu items with an optional non-interactive header. */
export function MenuGroup({ header, children }: { header?: ReactNode; children: ReactNode }) {
  return (
    <div role="group" aria-label={typeof header === "string" ? header : undefined} className="shrink-0 px-1 py-1 [&+&]:border-t [&+&]:border-outline-variant">
      {header && <div role="presentation" className="flex h-8 items-center px-3 text-label-m-em text-on-surface-variant">{header}</div>}
      <div className="flex flex-col gap-0.5">{children}</div>
    </div>
  );
}

export interface MenuItemProps {
  label: ReactNode;
  /** Second line (`text-body-m`, on-surface-variant). */
  supporting?: ReactNode;
  /** Trailing supporting text (mono label-s), e.g. `onset 4 s`, `In slot 2`. */
  meta?: ReactNode;
  /** Trailing chip before `meta` (e.g. a clip's label). */
  badge?: ReactNode;
  icon?: string;
  selected?: boolean;
  disabled?: boolean;
  /** Keyboard-highlighted option (listbox). */
  active?: boolean;
  mono?: boolean;
  onSelect?: () => void;
  id?: string;
  role?: "menuitem" | "option";
  /** Error / status rows (B-39, B-44) are not selectable. */
  tone?: "default" | "error";
}

/** Menu item: 44 px (56 two-line); selected = tertiary container with a leading check (the purple accent). */
export function MenuItem({ label, supporting, meta, badge, icon, selected, disabled, active, mono, onSelect, id, role = "menuitem", tone = "default" }: MenuItemProps) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => { if (active) ref.current?.scrollIntoView({ block: "nearest" }); }, [active]);
  const lead = selected ? "check" : icon;
  return (
    <div ref={ref} id={id} role={role} aria-selected={role === "option" ? !!selected : undefined} aria-disabled={disabled || undefined}
      tabIndex={role === "menuitem" ? -1 : undefined} data-active={active || undefined}
      onClick={() => { if (!disabled) onSelect?.(); }}
      onKeyDown={(e) => { if (role === "menuitem" && (e.key === "Enter" || e.key === " ") && !disabled) { e.preventDefault(); onSelect?.(); } }}
      className={`state-layer flex shrink-0 items-center gap-3 outline-none first:rounded-t-md last:rounded-b-md focus-visible:outline-none
        ${supporting ? "min-h-14 py-2" : "min-h-11"} ${lead ? "pl-3 pr-4" : "px-4"}
        ${selected ? "rounded-md bg-tertiary-container text-on-tertiary-container" : "rounded-xs text-on-surface"}
        ${disabled ? "cursor-default text-on-surface/38" : "cursor-pointer"} ${tone === "error" ? "text-critical-text" : ""}`}>
      {lead && <Icon name={lead} size={20} fill={selected} className={selected ? "" : disabled ? "" : "text-on-surface-variant"} />}
      <span className="min-w-0 flex-1">
        <span className={`block truncate text-body-l ${mono ? "font-mono text-body-m" : ""}`}>{label}</span>
        {supporting && <span className={`block truncate text-body-m ${selected ? "" : disabled ? "" : "text-on-surface-variant"}`}>{supporting}</span>}
      </span>
      {badge && <span className="shrink-0">{badge}</span>}
      {meta && <span className={`shrink-0 font-mono text-label-s ${selected || disabled ? "" : "text-on-surface-variant"}`}>{meta}</span>}
    </div>
  );
}
