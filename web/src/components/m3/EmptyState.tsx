import type { ReactNode } from "react";
import type { ShapeName } from "@/lib/shapes";
import { Icon } from "./Icon";
import { Shape } from "./Shape";

export interface EmptyStateProps {
  icon: string;
  /** Verbatim CONTRACT copy. */
  title: ReactNode;
  body?: ReactNode;
  /** Optional call to action (an M tonal button; S inside a feed column). */
  action?: ReactNode;
  /** Feed-column size: 64 px art. */
  compact?: boolean;
  shape?: ShapeName;
  /** Error states colour the icon critical-text. */
  tone?: "default" | "error";
  className?: string;
}

/** Centred empty state with expressive shape art and a tertiary accent dot (DESIGN §5.19, §2.4). */
export function EmptyState({ icon, title, body, action, compact, shape = "softBurst", tone = "default", className = "" }: EmptyStateProps) {
  const art = compact ? 64 : 96;
  return (
    <div className={`flex flex-col items-center justify-center px-6 text-center ${compact ? "py-4" : "py-10"} ${className}`}>
      <div className="relative grid place-items-center" style={{ width: art + (compact ? 12 : 24), height: art + (compact ? 12 : 24) }}>
        <Shape name={shape} size={art} className="text-surface-container-highest">
          <Icon name={icon} size={compact ? 28 : 40} className={tone === "error" ? "text-critical-text" : "text-on-surface-variant"} />
        </Shape>
        <Shape name="circle" size={compact ? 10 : 16} className={`absolute text-tertiary-container ${compact ? "right-1 top-1" : "right-2 top-2"}`} />
      </div>
      <div className={`mt-4 ${compact ? "text-title-m" : "text-title-l"} text-on-surface`}>{title}</div>
      {body && <div className="mt-1 max-w-[44ch] text-body-m text-on-surface-variant">{body}</div>}
      {action && <div className={compact ? "mt-4" : "mt-6"}>{action}</div>}
    </div>
  );
}
