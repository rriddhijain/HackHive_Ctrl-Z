"use client";
import { useState, type DragEvent, type ReactNode } from "react";
import type { Camera, Slot } from "@/lib/types";
import { FeedTile } from "./FeedTile";
import { NowLine } from "./NowLine";
import { SlotBadge } from "./SlotBadge";

export interface SlotColumnProps {
  slot: Slot;
  /** Header controls beside the slot badge: the source Select, and any message / progress under it. */
  controls: ReactNode;
  /** The camera in this slot (store.camInSlot(slot)); omit for an empty column. */
  cam?: Camera;
  /** Content of the empty 16:9 frame. */
  empty?: ReactNode;
  /** Details below the tile and its Now / meta lines (Clips: the Verdict). */
  children?: ReactNode;
  /** Enables drag-and-drop of a file onto the column (Clips upload, B-42). */
  onDropFile?: (f: File) => void;
  className?: string;
}

/**
 * One column of the Clips / Live 3-column frame (DESIGN §5.23, §6.2): header (slot badge + controls), the FeedTile,
 * then (with a camera) the Now and meta lines, then `children`. surface-container-low, 28 px corners, 12 px padding.
 */
export function SlotColumn({ slot, controls, cam, empty, children, onDropFile, className = "" }: SlotColumnProps) {
  const [drag, setDrag] = useState(0);
  const dnd = onDropFile ? {
    onDragEnter: (e: DragEvent) => { e.preventDefault(); setDrag((d) => d + 1); },
    onDragOver: (e: DragEvent) => e.preventDefault(),
    onDragLeave: () => setDrag((d) => Math.max(0, d - 1)),
    onDrop: (e: DragEvent) => { e.preventDefault(); setDrag(0); const f = e.dataTransfer.files[0]; if (f) onDropFile(f); },
  } : {};
  return (
    <section {...dnd} aria-label={`Slot ${slot}`} className={`flex min-w-0 flex-col gap-3 rounded-xl bg-surface-container-low p-3 ${className}`}>
      <div className="flex items-start gap-3">
        <div className="grid h-14 shrink-0 place-items-center pl-1"><SlotBadge slot={slot} /></div>
        <div className="min-w-0 flex-1">{controls}</div>
      </div>
      <FeedTile cam={cam} empty={empty} dropTarget={drag > 0} />
      {cam && <NowLine cam={cam} />}
      {children}
    </section>
  );
}
