"use client";
import { motion } from "motion/react";
import { useId, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { motionTokens } from "@/lib/motion";
import { Icon } from "./Icon";
import { LoadingIndicator } from "./LoadingIndicator";
import { Menu, MenuGroup, MenuItem } from "./Menu";

export interface SelectOption<V> {
  value: V;
  label: string;
  /** Second line in the menu. */
  supporting?: string;
  /** Trailing mono text (e.g. `onset 4 s`, `In slot 2`). */
  meta?: string;
  /** Trailing chip before `meta`. */
  badge?: ReactNode;
  icon?: string;
  disabled?: boolean;
  mono?: boolean;
}
export interface SelectGroup<V> { label?: string; options: SelectOption<V>[] }

export interface SelectProps<V> {
  /** Floating label above the value, e.g. `Slot 1 source`. */
  label: string;
  value: V | null | undefined;
  groups: SelectGroup<V>[];
  onChange: (value: V, option: SelectOption<V>) => void;
  /** Shown when nothing is selected. */
  placeholder?: string;
  /** Overrides the shown value text (e.g. an uploaded file not in the list). */
  valueLabel?: ReactNode;
  /** Second line under the value, e.g. `Fighting · onset 4 s · dev/fighting`. */
  supporting?: ReactNode;
  /** 24 px leading element (the slot shape badge). */
  leading?: ReactNode;
  /** Replaces the options with one non-selectable row (loading / error / empty copy, B-39, B-44). */
  status?: { kind: "loading" | "error" | "empty"; title: string; body?: string };
  disabled?: boolean;
  /** Value text in mono (clip file names, URLs). */
  mono?: boolean;
  onOpenChange?: (open: boolean) => void;
  className?: string;
}

/**
 * M3 Expressive Select (DESIGN §5.7): a 56 px anchor and a segmented Menu with listbox semantics.
 * Keyboard: Enter/Space/ArrowDown/ArrowUp open; arrows move (skipping disabled), Home/End, Enter selects,
 * Esc closes and refocuses the anchor, Tab closes; typeahead within 500 ms, repeated letter cycles.
 */
export function Select<V>({ label, value, groups, onChange, placeholder = "Choose…", valueLabel, supporting, leading, status, disabled, mono,
  onOpenChange, className = "" }: SelectProps<V>) {
  const id = useId();
  const anchor = useRef<HTMLButtonElement>(null);
  const [open, setOpen_] = useState(false);
  const [active, setActive] = useState(-1);
  const typed = useRef({ s: "", t: 0 });
  const flat = useMemo(() => (status ? [] : groups.flatMap((g) => g.options)), [groups, status]);
  const sel = flat.findIndex((o) => o.value === value);
  const current = sel >= 0 ? flat[sel] : undefined;
  const setOpen = (o: boolean) => { setOpen_(o); onOpenChange?.(o); if (o) setActive(sel >= 0 ? sel : flat.findIndex((x) => !x.disabled)); };
  const step = (from: number, d: 1 | -1) => {
    for (let k = 1; k <= flat.length; k++) { const i = (from + d * k + flat.length) % flat.length; if (!flat[i].disabled) return i; }
    return from;
  };
  const choose = (i: number) => { const o = flat[i]; if (!o || o.disabled) return; setOpen(false); anchor.current?.focus(); onChange(o.value, o); };
  const keys = (e: KeyboardEvent) => {
    if (disabled) return;
    if (!open) {
      if (["Enter", " ", "ArrowDown", "ArrowUp"].includes(e.key)) { e.preventDefault(); setOpen(true); }
      return;
    }
    if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => step(a, 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => step(a < 0 ? 0 : a, -1)); }
    else if (e.key === "Home") { e.preventDefault(); setActive(step(-1, 1)); }
    else if (e.key === "End") { e.preventDefault(); setActive(step(0, -1)); }
    else if (e.key === "Enter" || e.key === " ") { e.preventDefault(); if (active >= 0) choose(active); }
    else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); setOpen(false); }
    else if (e.key === "Tab") setOpen(false);
    else if (e.key.length === 1 && !e.metaKey && !e.ctrlKey && !e.altKey) {
      const now = Date.now(), t = typed.current, k = e.key.toLowerCase();
      t.s = now - t.t > 500 ? k : t.s + k; t.t = now;
      const same = [...t.s].every((c) => c === t.s[0]);
      const prefix = same ? t.s[0] : t.s;
      const start = same ? active : active - 1;
      for (let j = 1; j <= flat.length; j++) {
        const i = (start + j + flat.length) % flat.length;
        if (!flat[i].disabled && flat[i].label.toLowerCase().startsWith(prefix)) { setActive(i); break; }
      }
    }
  };
  let n = -1;
  return (
    <div className={`relative ${className}`}>
      <button ref={anchor} type="button" role="combobox" aria-haspopup="listbox" aria-expanded={open} aria-controls={open ? `${id}-lb` : undefined}
        aria-activedescendant={open && active >= 0 ? `${id}-o${active}` : undefined} aria-label={label} disabled={disabled} data-active={open || undefined}
        onClick={() => setOpen(!open)} onKeyDown={keys}
        className={`state-layer group flex min-h-14 w-full items-center gap-3 overflow-hidden rounded-lg bg-surface-container-high py-2 pl-3 pr-2 text-left
          disabled:text-on-surface/38`}>
        {leading && <span className="grid shrink-0 place-items-center">{leading}</span>}
        <span className="min-w-0 flex-1">
          <span className="block text-body-s text-on-surface-variant">{label}</span>
          <span title={typeof (valueLabel ?? current?.label) === "string" ? (valueLabel ?? current?.label) as string : undefined}
            className={`block truncate ${current || valueLabel ? "text-on-surface" : "text-on-surface-variant"} ${mono && (current || valueLabel) ? "font-mono text-body-m" : "text-body-l"}`}>
            {valueLabel ?? current?.label ?? placeholder}
          </span>
          {supporting && <span className="block truncate text-body-s text-on-surface-variant">{supporting}</span>}
        </span>
        <motion.span animate={{ rotate: open ? 180 : 0 }} transition={motionTokens.fast} className="grid size-10 shrink-0 place-items-center text-on-surface-variant">
          <Icon name="keyboard_arrow_down" size={24} />
        </motion.span>
        <span aria-hidden="true" className={`absolute inset-x-3 bottom-0 h-0.5 rounded-full bg-primary transition-opacity ${open ? "opacity-100" : "opacity-0 group-focus-visible:opacity-100"}`} />
      </button>
      <Menu open={open} onClose={() => setOpen(false)} anchor={anchor} role="listbox" id={`${id}-lb`} aria-label={label}
        aria-activedescendant={active >= 0 ? `${id}-o${active}` : undefined}>
        {status ? (
          <MenuGroup>
            <div role="option" aria-disabled="true" aria-selected={false} className={`flex min-h-14 items-center gap-3 px-4 py-3 ${status.kind === "error" ? "text-critical-text" : "text-on-surface-variant"}`}>
              {status.kind === "loading" ? <LoadingIndicator size={24} aria-label={status.title} /> : <Icon name={status.kind === "error" ? "error" : "info"} size={20} />}
              <span className="min-w-0">
                <span className="block text-body-l">{status.title}</span>
                {status.body && <span className="block text-body-s text-on-surface-variant">{status.body}</span>}
              </span>
            </div>
          </MenuGroup>
        ) : groups.filter((g) => g.options.length).map((g, gi) => (
          <MenuGroup key={g.label ?? gi} header={g.label}>
            {g.options.map((o) => {
              const i = ++n;
              return <MenuItem key={i} id={`${id}-o${i}`} role="option" label={o.label} supporting={o.supporting} meta={o.meta} badge={o.badge} icon={o.icon} mono={o.mono}
                selected={i === sel} disabled={o.disabled} active={i === active} onSelect={() => choose(i)} />;
            })}
          </MenuGroup>
        ))}
      </Menu>
    </div>
  );
}
