import type { ReactNode } from "react";

export type StatusVariant = "critical" | "high" | "ok" | "pending" | "error" | "neutral" | "mono" | "scrim";

const V: Record<StatusVariant, string> = {
  critical: "bg-critical text-on-critical",
  high: "bg-high text-on-high",
  ok: "bg-ok text-on-ok",
  pending: "bg-high-container text-on-high-container",
  error: "bg-critical-container text-on-critical-container",
  neutral: "bg-surface-container-highest text-on-surface-variant",
  mono: "bg-surface-container-highest text-on-surface-variant font-mono",
  scrim: "bg-scrim/56 text-white font-mono",   // on video (CLIP / LIVE)
};
export const DOT: Record<"ok" | "high" | "critical" | "neutral", string> = {
  ok: "bg-ok-dot", high: "bg-high", critical: "bg-critical", neutral: "bg-outline",
};

export interface StatusChipProps {
  variant: StatusVariant;
  children: ReactNode;
  /** Leading 6 px dot in a tone. */
  dot?: keyof typeof DOT;
  title?: string;
  className?: string;
}

/** Non-interactive status chip (DESIGN §5.11): 24 px, full radius, label-m emphasized. Severity always has text. */
export function StatusChip({ variant, children, dot, title, className = "" }: StatusChipProps) {
  return (
    <span title={title} className={`inline-flex h-6 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 text-label-m-em ${V[variant]} ${className}`}>
      {dot && <Dot tone={dot} />}{children}
    </span>
  );
}

/** A status / severity dot (non-text, ≥ 3:1). */
export function Dot({ tone, size = 6, className = "" }: { tone: keyof typeof DOT; size?: number; className?: string }) {
  return <span aria-hidden="true" style={{ width: size, height: size }} className={`inline-block shrink-0 rounded-full ${DOT[tone]} ${className}`} />;
}
