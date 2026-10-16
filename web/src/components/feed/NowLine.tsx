"use client";
import { ist, ms, pc, v } from "@/lib/format";
import { useLive } from "@/lib/store";
import type { Camera } from "@/lib/types";

/** B-26 `Now …` line (one line, full text as tooltip) and the B-27 mono meta line, straight from metrics. */
export function NowLine({ cam: c, className = "" }: { cam: Camera; className?: string }) {
  const cm = useLive().m?.cameras?.[c.id];
  return (
    <div className={`min-w-0 px-1 ${className}`}>
      <p className="truncate text-body-m text-on-surface" title={cm?.now?.text}><span className="text-on-surface-variant">Now </span>{cm?.now?.text ?? "—"}</p>
      <p className="mt-0.5 truncate font-mono text-body-s text-on-surface-variant">
        {c.id} · {v(cm?.people)} ppl · YOLO {ms(cm?.yolo_ms_p50)} · keep-up {pc(cm?.keep_up)} · as of {ist(cm?.now?.ts)} {cm?.now?.source ?? ""}
      </p>
    </div>
  );
}
