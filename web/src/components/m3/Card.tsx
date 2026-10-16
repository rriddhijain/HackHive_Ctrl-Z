import type { HTMLAttributes, ReactNode } from "react";

export interface CardProps extends Omit<HTMLAttributes<HTMLElement>, "className"> {
  variant?: "filled" | "outlined" | "elevated";
  /** Corner token: md 12 (cards), lg 16, lg-plus 20 (KPI, Verdict), xl 28 (columns, sections), xl-plus 32 (report, chat). */
  radius?: "md" | "lg" | "lg-plus" | "xl" | "xl-plus";
  /** Surface level for filled cards (the tonal ladder, §4.6). */
  level?: "low" | "default" | "high" | "highest";
  /** Adds the state layer (clickable cards). */
  interactive?: boolean;
  as?: "div" | "section" | "article" | "li";
  /** Layout and padding only. */
  className?: string;
  children?: ReactNode;
}

const R = { md: "rounded-md", lg: "rounded-lg", "lg-plus": "rounded-lg-plus", xl: "rounded-xl", "xl-plus": "rounded-xl-plus" };
const L = { low: "bg-surface-container-low", default: "bg-surface-container", high: "bg-surface-container-high", highest: "bg-surface-container-highest" };

/** M3 card surface (DESIGN §5.9). Filled uses surface-container by default (one step above a low section). */
export function Card({ variant = "filled", radius = "md", level = "default", interactive, as: Tag = "div", className = "", children, ...rest }: CardProps) {
  const v = variant === "outlined" ? "bg-surface border border-outline-variant"
    : variant === "elevated" ? "bg-surface-container-low shadow-level-1" : L[level];
  return <Tag {...rest} className={`${v} ${R[radius]} ${interactive ? "state-layer" : ""} ${className}`}>{children}</Tag>;
}
