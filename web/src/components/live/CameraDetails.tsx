"use client";
import type { ReactNode } from "react";
import { Card, Chip, Dot } from "@/components/m3";
import { sevTone } from "@/components/alert-bits";
import { camState, ms, pc, title, v } from "@/lib/format";
import { useLive, useStore } from "@/lib/store";
import type { Camera } from "@/lib/types";

const fps = (x: number | null | undefined) => (x == null ? "—" : x.toFixed(1));

/**
 * Details card under a Live tile: people, YOLO p50, keep-up, fps, status (all from SSE metrics), then this camera's
 * open alerts and its latest closed ones as chips that open the alert's report (/alerts/?id=).
 */
export function CameraDetails({ cam }: { cam: Camera }) {
  const { camStatus, camEvents, openEvent } = useStore();
  const { m } = useLive();
  const cm = m?.cameras?.[cam.id];
  const [tone, label] = camState(camStatus(cam), cam.source_type);
  const evs = camEvents(cam.id).filter((e) => e.status !== "dismissed").reverse();   // newest first
  const open = evs.filter((e) => e.status === "open");
  const shown = [...open, ...evs.filter((e) => e.status !== "open").slice(0, Math.max(0, 4 - open.length))];
  const facts: [string, ReactNode][] = [
    ["People", v(cm?.people)],
    ["YOLO p50", ms(cm?.yolo_ms_p50)],
    ["Keep-up", pc(cm?.keep_up)],
    ["FPS", fps(cm?.capture_fps)],
    ["Status", <span key="s" className="inline-flex items-center gap-1.5"><Dot tone={tone} />{label}</span>],
  ];
  return (
    <Card radius="lg-plus" className="p-4">
      <dl className="grid grid-cols-3 gap-x-4 gap-y-3 xl:grid-cols-5">
        {facts.map(([k, val]) => (
          <div key={k} className="min-w-0">
            <dt className="text-label-m text-on-surface-variant">{k}</dt>
            <dd className={`mt-0.5 truncate text-title-s text-on-surface ${k === "Status" ? "" : "font-mono"}`} title={k === "FPS" ? `capture ${fps(cm?.capture_fps)} · detector ${fps(cm?.det_fps)}` : undefined}>{val}</dd>
          </div>
        ))}
      </dl>
      <div className="mt-4 flex items-center justify-between">
        <h3 className="text-label-l-em text-on-surface-variant">Alerts from this camera</h3>
        {open.length > 0 && <span className="font-mono text-label-m text-on-surface-variant">{open.length} open</span>}
      </div>
      {shown.length ? (
        <div className="mt-2 flex flex-wrap gap-2">
          {shown.map((e) => (
            <Chip key={e.id} dense title={`Open event ${e.id}`} onClick={() => openEvent(e)}>
              <span className="inline-flex items-center gap-1.5">
                <Dot tone={e.status === "open" ? sevTone(e.severity) : "neutral"} />
                <span className="font-mono">#{e.id}</span> {title(e.category)}
              </span>
            </Chip>
          ))}
        </div>
      ) : (
        <p className="mt-1 text-body-s text-on-surface-variant">None yet</p>
      )}
    </Card>
  );
}
