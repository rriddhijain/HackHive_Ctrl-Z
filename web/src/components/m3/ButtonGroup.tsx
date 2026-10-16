"use client";
import { useRef, type KeyboardEvent } from "react";
import { Icon } from "./Icon";

export interface ButtonGroupOption<V extends string | number> { value: V; label: string; icon?: string; disabled?: boolean }
export interface ButtonGroupProps<V extends string | number> {
  options: ButtonGroupOption<V>[];
  value: V | undefined;
  onChange: (v: V) => void;
  /** Required radiogroup label (e.g. `Handover window`, `Camera`). */
  "aria-label": string;
  /** Labels in mono (camera ids). */
  mono?: boolean;
  className?: string;
}

/**
 * M3 Expressive connected button group, single-select (DESIGN §5.5): 40 px, 2 px gaps, outer corners full,
 * inner 8 px; the selected one is fully round and gains a check. Radiogroup with roving tabindex.
 */
export function ButtonGroup<V extends string | number>({ options, value, onChange, mono, className = "", ...aria }: ButtonGroupProps<V>) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const idx = Math.max(0, options.findIndex((o) => o.value === value));
  const move = (e: KeyboardEvent, i: number) => {
    const last = options.length - 1;
    const to = e.key === "ArrowRight" || e.key === "ArrowDown" ? (i === last ? 0 : i + 1)
      : e.key === "ArrowLeft" || e.key === "ArrowUp" ? (i === 0 ? last : i - 1)
      : e.key === "Home" ? 0 : e.key === "End" ? last : -1;
    if (to < 0 || options[to].disabled) return;
    e.preventDefault();
    refs.current[to]?.focus();
    onChange(options[to].value);
  };
  return (
    <div role="radiogroup" aria-label={aria["aria-label"]} className={`inline-flex h-10 gap-0.5 ${className}`}>
      {options.map((o, i) => {
        const on = o.value === value, first = i === 0, last = i === options.length - 1;
        const outer = 20, inner = on ? 20 : 8;
        const radius = { borderTopLeftRadius: first || on ? outer : inner, borderBottomLeftRadius: first || on ? outer : inner,
          borderTopRightRadius: last || on ? outer : inner, borderBottomRightRadius: last || on ? outer : inner };
        return (
          <button key={String(o.value)} ref={(el) => { refs.current[i] = el; }} type="button" role="radio" aria-checked={on}
            tabIndex={i === idx ? 0 : -1} disabled={o.disabled} onClick={() => onChange(o.value)} onKeyDown={(e) => move(e, i)}
            style={radius}
            className={`state-layer inline-flex items-center gap-1 px-4 text-label-l disabled:text-on-surface/38 ${mono ? "font-mono" : ""}
              ${on ? "bg-primary text-on-primary" : "bg-secondary-container text-on-secondary-container"}`}>
            {on && <span className="-ml-0.5 inline-flex"><Icon name="check" size={16} weight={500} /></span>}
            {o.icon && <Icon name={o.icon} size={18} />}
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
