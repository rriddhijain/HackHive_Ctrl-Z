import type { ReactNode } from "react";
import { shapePath, type ShapeName } from "@/lib/shapes";

export interface ShapeProps {
  name: ShapeName;
  size: number;
  /** Colour classes for the shape (fill = currentColor) and layout. */
  className?: string;
  /** Rotation in degrees. */
  rotate?: number;
  /** Content centred on the shape (a number, an icon). */
  children?: ReactNode;
}

/** An M3 Expressive shape (DESIGN §2.3, §2.4): logo, slot badges, KPI icons, empty states. */
export function Shape({ name, size, className = "", rotate = 0, children }: ShapeProps) {
  const svg = (
    <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size} aria-hidden="true" className={children ? "absolute inset-0" : className}
      style={rotate ? { transform: `rotate(${rotate}deg)` } : undefined}>
      <path d={shapePath(name, size)} fill="currentColor" />
    </svg>
  );
  if (!children) return svg;
  return (
    <span className={`relative inline-grid shrink-0 place-items-center ${className}`} style={{ width: size, height: size }}>
      {svg}<span className="relative">{children}</span>
    </span>
  );
}
