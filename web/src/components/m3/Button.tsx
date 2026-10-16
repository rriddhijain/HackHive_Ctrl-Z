"use client";
import type { AnchorHTMLAttributes, ButtonHTMLAttributes, MouseEvent, ReactNode } from "react";
import { Icon } from "./Icon";

export type ButtonVariant = "filled" | "tonal" | "outlined" | "text" | "elevated";
export type ButtonSize = "xs" | "s" | "m" | "l";
/** Colour set inside a severity container (notifications only, DESIGN §5.10). */
export type ButtonTone = "default" | "critical" | "high";

type Native = Omit<ButtonHTMLAttributes<HTMLButtonElement>, "style" | "className" | "children">;

export interface ButtonProps extends Native {
  variant?: ButtonVariant;
  size?: ButtonSize;
  shape?: "round" | "square";
  /** Leading Material Symbol. */
  icon?: string;
  trailingIcon?: string;
  /** Toggle button: selected fills primary and takes the square shape. */
  selected?: boolean;
  tone?: ButtonTone;
  /** Renders an <a> (e.g. the CSV export link). */
  href?: string;
  download?: AnchorHTMLAttributes<HTMLAnchorElement>["download"];
  /** Layout only. */
  className?: string;
  children?: ReactNode;
}

// Rest / square radii in px (DESIGN §2.2).
const SIZE = {
  xs: { h: "h-8", pad: "px-3", padNo: "px-4", gap: "gap-2", icon: 20, text: "text-label-l", round: 16, square: 12, hit: "after:-inset-y-2" },
  s: { h: "h-10", pad: "px-4", padNo: "px-4", gap: "gap-2", icon: 20, text: "text-label-l", round: 20, square: 12, hit: "after:-inset-y-1" },
  m: { h: "h-14", pad: "px-6", padNo: "px-6", gap: "gap-2", icon: 24, text: "text-title-m", round: 28, square: 16, hit: "" },
  l: { h: "h-24", pad: "px-12", padNo: "px-12", gap: "gap-3", icon: 32, text: "text-headline-s", round: 48, square: 28, hit: "" },
} as const;

const COLOR: Record<ButtonTone, Record<ButtonVariant, string>> = {
  default: {
    filled: "bg-primary text-on-primary",
    tonal: "bg-secondary-container text-on-secondary-container",
    outlined: "border border-outline-variant text-on-surface-variant",
    text: "text-primary",
    elevated: "bg-surface-container-low text-primary shadow-level-1 hover:shadow-level-2",
  },
  critical: {   // on a #D93025 container: white button with red label, white outline
    filled: "bg-on-critical text-critical", tonal: "bg-on-critical text-critical",
    outlined: "border border-on-critical/70 text-on-critical", text: "text-on-critical", elevated: "bg-on-critical text-critical",
  },
  high: {       // on a #F9AB00 container: #202124 button with amber label
    filled: "bg-on-high text-high", tonal: "bg-on-high text-high",
    outlined: "border border-on-high/60 text-on-high", text: "text-on-high", elevated: "bg-on-high text-high",
  },
};
const DISABLED: Record<ButtonVariant, string> = {
  filled: "bg-on-surface/12 text-on-surface/38", tonal: "bg-on-surface/12 text-on-surface/38", elevated: "bg-on-surface/12 text-on-surface/38",
  outlined: "border border-on-surface/12 text-on-surface/38", text: "text-on-surface/38",
};
const DISABLED_TONE: Record<ButtonVariant, string> = {
  filled: "bg-current/12 opacity-60", tonal: "bg-current/12 opacity-60", elevated: "bg-current/12 opacity-60",
  outlined: "border border-current/30 opacity-60", text: "opacity-60",
};

/**
 * M3 Expressive button (DESIGN §5.3). No press morph (basic motion): the state layer gives the feedback.
 * `disabled` renders aria-disabled (still focusable, so a Tooltip can explain why) and blocks clicks.
 */
export function Button({ variant = "filled", size = "s", shape = "round", icon, trailingIcon, selected, tone = "default", href, download,
  className = "", children, disabled, onClick, type = "button", ...rest }: ButtonProps) {
  const s = SIZE[size];
  const rest_ = shape === "square" || selected ? s.square : s.round;
  const toggle = selected !== undefined;
  const color = disabled ? (tone === "default" ? DISABLED[variant] : `${COLOR[tone][variant]} ${DISABLED_TONE[variant]}`)
    : toggle ? (selected ? "bg-primary text-on-primary" : "bg-surface-container-high text-on-surface-variant")
    : COLOR[tone][variant];
  const cls = `state-layer inline-flex shrink-0 select-none items-center justify-center whitespace-nowrap ${s.h} ${icon ? s.pad : s.padNo} ${s.gap} ${s.text} ${color}
    after:absolute after:inset-x-0 after:content-[''] ${s.hit} ${disabled ? "cursor-default" : ""} ${className}`;
  const body = (
    <>
      {icon && <Icon name={icon} size={s.icon} fill={selected} weight={500} />}
      {children}
      {trailingIcon && <Icon name={trailingIcon} size={s.icon} weight={500} />}
    </>
  );
  const style = { borderRadius: rest_ };
  const click = (e: MouseEvent<HTMLButtonElement & HTMLAnchorElement>) => {
    if (disabled) { e.preventDefault(); return; }
    onClick?.(e as MouseEvent<HTMLButtonElement>);
  };
  if (href) {
    return <a style={style} href={disabled ? undefined : href} download={download} aria-disabled={disabled || undefined} onClick={click} className={cls}>{body}</a>;
  }
  return (
    <button {...rest} style={style} type={type} aria-disabled={disabled || undefined} aria-pressed={toggle ? selected : undefined}
      onClick={click} className={cls}>{body}</button>
  );
}
