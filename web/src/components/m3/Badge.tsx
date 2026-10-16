export interface BadgeProps {
  /** Large badge with a number (hidden at 0); omit for the 6 px dot. */
  count?: number;
  tone?: "primary" | "critical";
  /** Positioning on a `relative` wrapper. */
  className?: string;
}

/** M3 badge (DESIGN §5.12); > 99 shows 99+. Static (basic motion). */
export function Badge({ count, tone = "primary", className = "" }: BadgeProps) {
  if (count !== undefined && count <= 0) return null;
  const color = tone === "critical" ? "bg-critical text-on-critical" : "bg-primary text-on-primary";
  return (
    <span className={`pointer-events-none inline-grid place-items-center rounded-full ${count === undefined ? "size-1.5" : "h-4 min-w-4 px-1 text-label-s"} ${color} ${className}`}>
      {count !== undefined && (count > 99 ? "99+" : count)}
    </span>
  );
}
