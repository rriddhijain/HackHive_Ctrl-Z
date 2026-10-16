import type { CSSProperties } from "react";

export interface IconProps {
  /** Material Symbols Rounded ligature name (checked against material-symbols 0.48.0). */
  name: string;
  /** Rendered size in px; also the optical size axis. */
  size?: number;
  /** FILL axis: 1 for the active tab, a selected toggle, severity and notification icons. */
  fill?: boolean;
  weight?: number;
  /** Layout only (margin, placement). Colour comes from the text colour of the parent. */
  className?: string;
}

/** Decorative Material Symbols glyph (aria-hidden; the control carries the label). GRAD follows the theme. */
export function Icon({ name, size = 24, fill = false, weight = 400, className = "" }: IconProps) {
  const style = {
    fontSize: size, width: size, height: size,
    "--icon-fill": fill ? 1 : 0, "--icon-wght": weight, "--icon-opsz": Math.min(48, Math.max(20, size)),
  } as CSSProperties;
  return <span aria-hidden="true" className={`material-symbols-rounded shrink-0 overflow-hidden ${className}`} style={style}>{name}</span>;
}
