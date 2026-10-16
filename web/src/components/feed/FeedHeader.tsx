"use client";
import { Button, Icon, Tooltip } from "@/components/m3";
import { useStore } from "@/lib/store";
import type { Mode } from "@/lib/types";

const OVERLOAD = { live: "3+ live cameras: alerts may slow", clips: "3 clips at once: alerts may slow" };

/**
 * The 40 px row above the Clips / Live columns: B-18 label + running count, the B-19 overload warning (3 sources, both
 * tabs, §4.3) and the §4.2 mode-mismatch notice with a switch button (same confirm rule as entering the tab).
 */
export function FeedHeader({ mode, className = "" }: { mode: Mode; className?: string }) {
  const { cams, camStatus, mode: serverMode, requestMode } = useStore();
  const other = serverMode && serverMode !== mode;
  // Clips: count only clips still playing (a finished one stays listed until replaced). Live: every source (old B-19).
  const running = mode === "clips" ? cams.filter((c) => !["ended", "stopped", "down"].includes(camStatus(c))).length : cams.length;
  return (
    <div className={`flex min-h-10 flex-wrap items-center gap-x-3 gap-y-2 ${className}`}>
      <h2 className="text-title-s-em text-on-surface">{mode === "live" ? "Live sources" : "Now playing"}</h2>
      <span className="font-mono text-label-m text-on-surface-variant">{running}</span>
      {running > 2 && !other && (
        <Tooltip content="P2b: 3 busy sources pushed GPU duty above 90 %">
          <span tabIndex={0} className="inline-flex h-8 items-center gap-1.5 rounded-full bg-high-container px-3 text-label-l text-on-high-container">
            <Icon name="warning" size={18} fill />{OVERLOAD[mode]}
          </span>
        </Tooltip>
      )}
      {other && (
        <span role="status" className="ml-auto inline-flex min-h-10 items-center gap-3 rounded-full bg-high-container py-1 pl-4 pr-1 text-body-m text-on-high-container">
          <Icon name="warning" size={18} fill />
          {`The server is in ${serverMode === "live" ? "Live" : "Clips"} mode`}
          <Button size="xs" variant="filled" onClick={() => requestMode(mode)}>{`Switch to ${mode === "live" ? "Live" : "Clips"}`}</Button>
        </span>
      )}
    </div>
  );
}
