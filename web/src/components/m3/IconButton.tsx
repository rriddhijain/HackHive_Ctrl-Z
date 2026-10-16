"use client";
import type { ButtonHTMLAttributes, MouseEvent } from "react";
import { Icon } from "./Icon";
import { Tooltip } from "./Tooltip";

type Native = Omit<ButtonHTMLAttributes<HTMLButtonElement>, "style" | "className" | "children" | "aria-label">;

export interface IconButtonProps extends Native {
  icon: string;
  /** Required: also the plain tooltip unless `tooltip` overrides it. */
  "aria-label": string;
  variant?: "standard" | "filled" | "tonal" | "outlined";
  size?: "xs" | "s";
  width?: "default" | "narrow" | "wide";
  /** Toggle: selected fills the icon and takes the square shape (DESIGN §2.2). */
  selected?: boolean;
  /** Tooltip text; `false` for none. Defaults to aria-label. */
  tooltip?: string | false;
  /** Severity container the button sits on (notification close). */
  tone?: "default" | "critical" | "high" | "scrim";
  className?: string;
}

const SZ = { xs: { box: 32, icon: 20, round: 16, square: 12 }, s: { box: 40, icon: 24, round: 20, square: 12 } };
const SIDE = { xs: { default: 6, narrow: 4, wide: 10 }, s: { default: 8, narrow: 4, wide: 14 } };

/** M3 Expressive icon button (DESIGN §5.4), 48 px hit area, optional toggle (no press morph). */
export function IconButton({ icon, variant = "standard", size = "s", width = "default", selected, tooltip, tone = "default",
  className = "", disabled, onClick, type = "button", ...rest }: IconButtonProps) {
  const s = SZ[size];
  const toggle = selected !== undefined;
  const color = disabled ? (variant === "standard" ? "text-on-surface/38" : variant === "outlined" ? "border border-on-surface/12 text-on-surface/38" : "bg-on-surface/12 text-on-surface/38")
    : tone === "critical" ? "text-on-critical" : tone === "high" ? "text-on-high" : tone === "scrim" ? "bg-scrim/48 text-white"
    : variant === "standard" ? (selected ? "text-primary" : "text-on-surface-variant")
    : variant === "filled" ? (toggle && !selected ? "bg-surface-container-highest text-primary" : "bg-primary text-on-primary")
    : variant === "tonal" ? (toggle && !selected ? "bg-surface-container-highest text-on-surface-variant" : "bg-secondary-container text-on-secondary-container")
    : selected ? "bg-inverse-surface text-inverse-on-surface" : "border border-outline-variant text-on-surface-variant";
  const r = toggle && selected ? s.square : s.round;
  const label = rest["aria-label"];
  const btn = (
    <button {...rest} type={type} aria-disabled={disabled || undefined} aria-pressed={toggle ? selected : undefined}
      onClick={(e: MouseEvent<HTMLButtonElement>) => { if (!disabled) onClick?.(e); }}
      style={{ borderRadius: r, height: s.box, width: s.box - 2 * SIDE[size].default + 2 * SIDE[size][width] }}
      className={`state-layer inline-grid shrink-0 place-items-center after:absolute after:-inset-1 after:content-[''] ${color} ${disabled ? "cursor-default" : ""} ${className}`}>
      <Icon name={icon} size={s.icon} fill={selected || variant === "filled" || tone === "scrim"} />
    </button>
  );
  return tooltip === false ? btn : <Tooltip content={tooltip ?? label}>{btn}</Tooltip>;
}
