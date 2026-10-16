import { Shape } from "@/components/m3";
import type { ShapeName } from "@/lib/shapes";
import type { Slot } from "@/lib/types";

const SHAPE: Record<Slot, ShapeName> = { 1: "cookie4", 2: "clover4", 3: "sunny" };

/** Slot number on its expressive shape (DESIGN §2.4): 1 cookie4, 2 clover4, 3 sunny; secondary container. */
export function SlotBadge({ slot, size = 28 }: { slot: Slot; size?: number }) {
  return (
    <Shape name={SHAPE[slot]} size={size} className="text-secondary-container">
      <span className="text-title-s-em text-on-secondary-container" aria-label={`Slot ${slot}`}>{slot}</span>
    </Shape>
  );
}
