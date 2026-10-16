"use client";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { AlertActions, SeverityChip, Top3Bar, sevTone, useTop3 } from "@/components/alert-bits";
import { Button, Card, Divider, Dot, EmptyState, IconButton, Skeleton, SkeletonLines, StatusChip } from "@/components/m3";
import { api } from "@/lib/api";
import { conf, ist, media, ms, pc, startTs, statusWord, title } from "@/lib/format";
import { useStore } from "@/lib/store";
import type { Event, Observation } from "@/lib/types";
import { HistoryChip } from "./AlertCard";

/** Report surface: surface-container-low, 32 px corners (DESIGN §6.3). */
function Surface({ children, id }: { children: ReactNode; id?: number }) {
  return <Card radius="xl-plus" level="low" className="p-6" {...(id != null ? { "data-event-card": id } : {})}>{children}</Card>;
}

function Fact({ label, children, mono }: { label: string; children: ReactNode; mono?: boolean }) {
  return (
    <div className="min-w-0 rounded-lg bg-surface-container px-4 py-3">
      <div className="text-label-m text-on-surface-variant">{label}</div>
      <div className={`mt-1 truncate text-title-s text-on-surface ${mono ? "font-mono" : ""}`}>{children}</div>
    </div>
  );
}

function Frame({ src, alt, caption }: { src: string; alt: string; caption?: string }) {
  return (
    <figure className="min-w-0">
      <img src={media(src)} alt={alt} className="aspect-video w-full rounded-lg bg-black object-contain" />
      {caption && <figcaption className="mt-1.5 text-label-m text-on-surface-variant">{caption}</figcaption>}
    </figure>
  );
}

/** Observation timeline from GET /api/events/{id}: null loading · false error · rows (ts ascending). */
function useObservations(e: Event): Observation[] | null | false {
  const [obs, setObs] = useState<{ id: number; rows: Observation[] | false } | null>(null);
  useEffect(() => {
    let alive = true;
    api.event(e.id).then((d) => alive && setObs({ id: e.id, rows: d.observations ?? [] })).catch(() => alive && setObs({ id: e.id, rows: false }));
    return () => { alive = false; };
  }, [e.id, e.n_obs]);
  return obs?.id === e.id ? obs.rows : null;
}

function Timeline({ event }: { event: Event }) {
  const obs = useObservations(event);
  return (
    <section aria-label="Observations" aria-busy={obs === null || undefined}>
      <h3 className="text-title-s-em text-on-surface">Observations</h3>
      {obs === null ? (
        <div className="mt-3 flex flex-col gap-3">{[0, 1].map((i) => <SkeletonLines key={i} lines={2} />)}</div>
      ) : obs === false ? (
        <p className="mt-2 text-body-m text-critical-text">Could not load the observations</p>
      ) : !obs.length ? (
        <p className="mt-2 text-body-m text-on-surface-variant">No observations</p>
      ) : (
        <ol className="mt-3 flex flex-col">
          {obs.map((o, i) => {
            const trigger = typeof o.trigger === "string" ? o.trigger : null;
            const cat = typeof o.category === "string" ? o.category : "";
            const c = typeof o.confidence === "number" ? o.confidence : null;
            const summary = typeof o.summary === "string" ? o.summary : null;
            return (
              <li key={o.id ?? i} className="relative grid grid-cols-[5.5rem_minmax(0,1fr)] gap-x-4 pb-4 last:pb-0">
                <span className="pt-0.5 font-mono text-body-s text-on-surface-variant">{ist(o.ts)}</span>
                <div className="relative min-w-0 border-l-2 border-outline-variant pl-4">
                  <Dot tone={cat === event.category ? sevTone(event.severity) : "neutral"} size={10}
                    className="absolute -left-1.5 top-1.5 ring-2 ring-surface-container-low" />
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-body-m-em text-on-surface">{title(cat) || "—"}</span>
                    <span className="font-mono text-body-s text-on-surface-variant">{pc(c)}</span>
                    {trigger && <StatusChip variant="mono">{trigger}</StatusChip>}
                  </div>
                  {summary && <p className="mt-1 text-body-m text-on-surface-variant">{summary}</p>}
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}

/** The individual report of one alert (B-63…B-67, CONTRACT §4.6). */
export function AlertReport({ event: e, onClose }: { event: Event; onClose: () => void }) {
  const { camName } = useStore();
  const top3 = useTop3(e);
  const box = useRef<HTMLDivElement>(null);
  const [frame, mosaic] = e.keyframe_paths ?? [];
  // B-64: the close control takes focus when a report opens (without scrolling the page).
  useEffect(() => { box.current?.querySelector<HTMLButtonElement>('button[aria-label="Close"]')?.focus({ preventScroll: true }); }, [e.id]);
  return (
    <div ref={box}>
      <Surface id={e.id}>
        <header className="flex items-center gap-3">
          <Dot tone={sevTone(e.severity)} size={10} />
          <h2 className="min-w-0 truncate text-headline-s-em text-on-surface">{title(e.category)}</h2>
          <SeverityChip severity={e.severity} />
          <span className="font-mono text-title-s text-on-surface-variant">#{e.id}</span>
          {!!e.seeded && <HistoryChip />}
          <div className="-mr-2 ml-auto"><IconButton icon="close" aria-label="Close" onClick={onClose} /></div>
        </header>

        {frame ? (
          <div className={`mt-5 grid gap-4 ${mosaic ? "wide:grid-cols-[3fr_2fr]" : ""}`}>
            <Frame src={frame} alt={`Key frame of event ${e.id}`} caption={mosaic ? "Key frame" : undefined} />
            {mosaic && <Frame src={mosaic} alt={`Mosaic of event ${e.id}`} caption="Mosaic" />}
          </div>
        ) : !e.seeded && (
          <div className="mt-5 grid aspect-video w-full place-items-center rounded-lg bg-surface-container text-body-m text-on-surface-variant">
            No key frame yet
          </div>
        )}

        <div className="mt-5">
          {e.summary == null ? <SkeletonLines lines={2} /> : <p className="text-body-l text-on-surface">{e.summary}</p>}
        </div>
        <Top3Bar top3={top3} className="mt-4" />

        <div className="mt-5 grid grid-cols-2 gap-2 xl:grid-cols-3">
          <Fact label="Camera">{camName(e)}</Fact>
          <Fact label="Time" mono>{`${ist(startTs(e))} IST`}</Fact>
          <Fact label="Confidence" mono>{pc(conf(e)) + (e.alert?.rating ? ` ${e.alert.rating}` : "")}</Fact>
          <Fact label="Trigger → alert" mono>{ms(e.time_to_alert_ms)}</Fact>
          <Fact label="Onset → alert" mono>{ms(e.alert?.onset_to_alert_ms)}</Fact>
          <Fact label="Status">{statusWord(e.status)}</Fact>
        </div>

        <Divider className="my-6" />
        <Timeline event={e} />

        <div className="mt-6 flex justify-end">
          <AlertActions event={e} size="s" />
        </div>
      </Surface>
    </div>
  );
}

/** Report placeholder while GET /api/events/{id} runs. */
export function ReportSkeleton() {
  return (
    <Surface>
      <div aria-busy="true" aria-label="Loading the alert">
        <Skeleton className="h-7 w-1/2" />
        <Skeleton className="mt-5 aspect-video w-full" radius="lg" />
        <SkeletonLines lines={2} className="mt-5" />
        <div className="mt-5 grid grid-cols-2 gap-2 xl:grid-cols-3">
          {Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-16" radius="lg" />)}
        </div>
      </div>
    </Surface>
  );
}

/** Nothing selected, or an id the server does not know (404). */
export function ReportEmpty({ id, error, onClose }: { id?: number; error?: boolean; onClose: () => void }) {
  return (
    <Surface>
      {error ? (
        <EmptyState tone="error" icon="error" title={`Could not load alert #${id}`} body="Check the server is running, then reload the page."
          action={<Button variant="tonal" icon="arrow_back" onClick={onClose}>Back to alerts</Button>} />
      ) : id == null ? (
        <EmptyState icon="notifications" title="No alert selected" shape="cookie9" />
      ) : (
        <EmptyState icon="search_off" title={`Alert #${id} not found`} body="Choose an alert from the list."
          action={<Button variant="tonal" icon="arrow_back" onClick={onClose}>Back to alerts</Button>} />
      )}
    </Surface>
  );
}
