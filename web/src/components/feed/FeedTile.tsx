"use client";
import { motion } from "motion/react";
import type { ReactNode } from "react";
import { IconButton, LoadingIndicator, StatusChip, Dot } from "@/components/m3";
import { camState, conf, pc, title } from "@/lib/format";
import { motionTokens } from "@/lib/motion";
import { useStore } from "@/lib/store";
import type { Camera } from "@/lib/types";
import { LiveImage } from "./LiveImage";

export interface FeedTileProps {
  /** The source shown; omit for an empty slot. */
  cam?: Camera;
  /** Content of an empty 16:9 frame (an EmptyState, compact). */
  empty?: ReactNode;
  /** A file is dragged over the column (upload drop target). */
  dropTarget?: boolean;
  className?: string;
}

/**
 * 16:9 feed tile (B-20..B-25, DESIGN §5.23): letterboxed live image, status pill with dot, CLIP/LIVE badge, stop,
 * the hot-event chip and inset ring, and the connecting / down overlays. Reads status and hot event from the store.
 */
export function FeedTile({ cam: c, empty, dropTarget, className = "" }: FeedTileProps) {
  const { camStatus, hot: hotOf, removeSource } = useStore();
  const drop = dropTarget ? "shadow-level-4 outline-2 -outline-offset-2 outline-dashed outline-primary" : "";
  if (!c) {
    return (
      <div className={`relative grid aspect-video place-items-center overflow-hidden rounded-lg bg-surface-container ${drop} ${className}`}>
        {dropTarget && <div className="absolute inset-0 bg-primary-container/16" />}
        <div className="relative">{empty}</div>
      </div>
    );
  }
  const status = camStatus(c);
  const [tone, label] = camState(status, c.source_type);
  const hot = hotOf(c.id);
  const ring = hot?.severity === "critical" ? "ring-critical" : "ring-high";
  return (
    <div className={`relative aspect-video overflow-hidden rounded-lg bg-black ${drop} ${className}`}>
      {status === "connecting" ? <div className="aspect-video bg-black" /> : <LiveImage key={c.id} id={c.id} alt={c.name} />}
      {status === "connecting" && (
        <div className="absolute inset-0 grid place-items-center bg-surface-container-lowest">
          <div className="flex flex-col items-center gap-3">
            <LoadingIndicator contained size={48} aria-label="Connecting" />
            <span className="text-label-l text-on-surface-variant">Connecting…</span>
          </div>
        </div>
      )}
      {status === "down" && (
        <div className="absolute inset-0 grid place-items-center bg-scrim/60 text-center text-white">
          <div><div className="text-title-m">Source down</div><div className="mt-1 text-body-s opacity-80">Stop it, then add it again.</div></div>
        </div>
      )}
      {dropTarget && <div className="absolute inset-0 bg-primary-container/16" />}
      {hot && (
        <StatusChip variant={hot.severity === "critical" ? "critical" : "high"} className="absolute left-3 top-3">
          {title(hot.category)} · <span className="font-mono">{pc(conf(hot))}</span>
        </StatusChip>
      )}
      <div className="absolute right-3 top-3 flex items-center gap-1.5">
        <StatusChip variant="scrim">{c.source_type === "file" ? "CLIP" : "LIVE"}</StatusChip>
        <IconButton size="xs" icon="stop" tone="scrim" aria-label={`Stop ${c.name}`} tooltip="Stop and release this source" onClick={() => void removeSource(c.id)} />
      </div>
      <div className="absolute bottom-3 left-3 flex h-7 max-w-[calc(100%-24px)] items-center gap-2 rounded-full bg-scrim/56 px-3 text-label-m text-white">
        <Dot tone={tone} /><span className="font-mono">{c.id}</span><span className="truncate">· {c.name}</span><span className="whitespace-nowrap opacity-75">{label}</span>
      </div>
      <motion.div aria-hidden="true" initial={false} animate={{ opacity: hot ? 1 : 0 }} transition={motionTokens.fast}
        className={`pointer-events-none absolute inset-0 rounded-lg ring-2 ring-inset ${ring}`} />
    </div>
  );
}
