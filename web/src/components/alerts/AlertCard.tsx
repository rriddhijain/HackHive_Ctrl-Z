"use client";
import { AlertActions, SEEDED_TIP, SeverityChip, Top3Bar, sevTone, useTop3 } from "@/components/alert-bits";
import { ListItem, Skeleton, SkeletonLines, StatusChip, Tooltip } from "@/components/m3";
import { conf, ist, media, ms, pc, startTs, title } from "@/lib/format";
import { useStore } from "@/lib/store";
import type { Event } from "@/lib/types";

const STRIPE = { critical: "bg-critical", high: "bg-high", neutral: "bg-outline" };

/** `History` chip for seeded rows (B-54), tooltip `Seeded demo history (E-19)`. */
export function HistoryChip() {
  return <Tooltip content={SEEDED_TIP}><StatusChip variant="neutral">History</StatusChip></Tooltip>;
}

/** Confidence line of B-55: `91% High (peak 94%)`. */
export const confLine = (e: Event) =>
  pc(conf(e)) + (e.alert?.rating ? ` ${e.alert.rating}` : "")
  + (e.alert && e.peak_confidence != null && e.peak_confidence > e.alert.confidence ? ` (peak ${pc(e.peak_confidence)})` : "");

export interface AlertCardProps {
  event: Event;
  selected: boolean;
  onOpen: (id: number) => void;
}

/** One alert in the list (B-52…B-58): stripe, thumbnail, title row, camera + confidence, summary, top 3, latencies, two actions. */
export function AlertCard({ event: e, selected, onOpen }: AlertCardProps) {
  const { camName } = useStore();
  const top3 = useTop3(e);
  const frame = e.keyframe_paths?.[0];
  const hotCritical = e.status === "open" && e.severity === "critical";
  const o2a = e.alert?.onset_to_alert_ms;
  return (
    <ListItem selected={selected} tone={hotCritical ? "critical" : "default"} onClick={() => onOpen(e.id)} className="pl-6">
      <span aria-hidden="true" className={`absolute inset-y-3 left-2 w-1 rounded-full ${STRIPE[sevTone(e.severity)]}`} />
      <div className="flex gap-4">
        {frame ? (
          <img src={media(frame)} alt="" className="aspect-video w-24 shrink-0 self-start rounded-sm bg-black object-contain" />
        ) : !e.seeded && <Skeleton className="aspect-video w-24 shrink-0 self-start" radius="sm" />}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            {/* The title is the card's keyboard / screen-reader control; a click anywhere on the card bubbles to the row. */}
            <button type="button" aria-current={selected || undefined}
              className="min-w-0 truncate rounded-xs text-left text-title-m-em focus-visible:outline-offset-2">
              {title(e.category)}
            </button>
            <SeverityChip severity={e.severity} />
            {!!e.seeded && <HistoryChip />}
            <span className="ml-auto shrink-0 font-mono text-body-s opacity-80">{ist(startTs(e))}</span>
          </div>
          <div className="mt-0.5 flex min-w-0 items-baseline gap-2 text-body-m opacity-80">
            <span className="truncate">{camName(e)}</span>
            <span className="shrink-0 font-mono text-body-s">{confLine(e)}</span>
          </div>
        </div>
      </div>
      {e.summary == null
        ? <SkeletonLines lines={2} className="mt-3" />
        : <p className="mt-2 text-body-m">{e.summary}</p>}
      <Top3Bar top3={top3} className="mt-3" />
      <div className="mt-3 flex flex-wrap items-center justify-end gap-x-3 gap-y-2">
        <div className="mr-auto flex flex-wrap gap-1.5">
          {e.time_to_alert_ms != null && <StatusChip variant="mono">{`trigger → alert ${ms(e.time_to_alert_ms)}`}</StatusChip>}
          {o2a != null && <StatusChip variant="mono">{`onset → alert ${ms(o2a)}`}</StatusChip>}
        </div>
        <AlertActions event={e} />
      </div>
    </ListItem>
  );
}
