import type { HTMLAttributes, MouseEvent, ReactNode } from "react";

export interface ListProps extends Omit<HTMLAttributes<HTMLUListElement>, "className"> {
  children: ReactNode;
  className?: string;
}

/** M3 Expressive segmented list (DESIGN §5.13): one group, large outer corners, 2 px gaps. */
export function List({ children, className = "", ...rest }: ListProps) {
  return <ul {...rest} className={`flex flex-col gap-0.5 overflow-hidden rounded-lg ${className}`}>{children}</ul>;
}

export interface ListItemProps {
  children: ReactNode;
  selected?: boolean;
  /** Open critical alert: critical-container background (B-52). */
  tone?: "default" | "critical";
  onClick?: (e: MouseEvent<HTMLLIElement>) => void;
  /** Extra attributes, e.g. data-event-card. */
  data?: Record<`data-${string}`, string | number>;
  className?: string;
}

/** Segmented list item: inner corners 4 px, selected 16. Min 72 px. No motion (basic motion, captain 19:15). */
export function ListItem({ children, selected, tone = "default", onClick, data, className = "" }: ListItemProps) {
  const bg = selected ? "bg-secondary-container text-on-secondary-container" : tone === "critical" ? "bg-critical-container" : "bg-surface-container";
  return (
    <li {...data} onClick={onClick}
      className={`state-layer relative min-h-18 px-4 py-3 ${selected ? "rounded-lg" : "rounded-xs"} ${onClick ? "cursor-pointer" : ""} ${bg} ${className}`}>
      {children}
    </li>
  );
}
