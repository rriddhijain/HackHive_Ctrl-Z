"use client";
import type { MouseEvent, ReactNode } from "react";
import { Icon } from "./Icon";

export interface ChipProps {
  /** assist: citations `#12` · suggestion: Ask suggestions · filter / input: not used in v1. */
  type?: "assist" | "filter" | "input" | "suggestion";
  children: ReactNode;
  icon?: string;
  /** 24 px inside cards and chat. */
  dense?: boolean;
  mono?: boolean;
  selected?: boolean;
  disabled?: boolean;
  onClick?: (e: MouseEvent<HTMLButtonElement>) => void;
  /** Input chips: trailing close. */
  onRemove?: () => void;
  title?: string;
  /** Long labels wrap instead of truncating (Ask suggestions). */
  wrap?: boolean;
  className?: string;
}

/** M3 chip (DESIGN §5.11): small-8 radius, 32 px (24 dense). */
export function Chip({ type = "assist", children, icon, dense, mono, selected, disabled, onClick, onRemove, title, wrap, className = "" }: ChipProps) {
  const on = type === "filter" && selected;
  const color = disabled ? "border border-on-surface/12 text-on-surface/38"
    : on ? "bg-secondary-container text-on-secondary-container"
    : `border border-outline-variant ${type === "suggestion" ? "text-on-surface-variant" : "text-on-surface"}`;
  return (
    <button type="button" title={title} disabled={disabled} onClick={onClick} aria-pressed={type === "filter" ? !!selected : undefined}
      className={`state-layer inline-flex shrink-0 items-center gap-2 rounded-sm align-middle ${dense ? "h-6 px-2 text-label-m" : wrap ? "h-auto min-h-8 px-4 py-1.5 text-left text-label-l" : "h-8 px-4 text-label-l"}
        ${icon || on ? (dense ? "pl-1.5" : "pl-2") : ""} ${mono ? "font-mono" : ""} ${color} ${className}`}>
      {on ? <Icon name="check" size={18} /> : icon && <Icon name={icon} size={dense ? 16 : 18} className={disabled ? "" : "text-primary"} />}
      <span className={wrap ? "whitespace-normal" : "truncate"}>{children}</span>
      {type === "input" && onRemove && (
        <span role="button" aria-label="Remove" onClick={(e) => { e.stopPropagation(); onRemove(); }} className="-mr-2 grid size-6 place-items-center rounded-full">
          <Icon name="close" size={18} />
        </span>
      )}
    </button>
  );
}
