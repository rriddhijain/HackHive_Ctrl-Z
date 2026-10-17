"use client";
import { useEffect, useState, type ReactNode } from "react";
import { sevTone } from "@/components/alert-bits";
import { Card, Divider, Dot, Icon, Shape, SkeletonLines, StatusChip, type StatusVariant } from "@/components/m3";
import { ms, pc, title } from "@/lib/format";
import { useStore } from "@/lib/store";
import type { Camera, Event } from "@/lib/types";

/** A short clip can end while the model is still on its last frames: its alert may land seconds later (D86). */
const GRACE_MS = 20_000;

/** B-32 state word → chip variant (DESIGN §5.23). */
function stateOf(done: boolean, finishing: boolean, c: Camera, evs: Event[], hit: Event | undefined): [StatusVariant, string] {
  if (!done) return ["pending", "Running"];
  if (!c.label) return ["neutral", "Unlabelled"];
  if (c.label === "normal") return evs.length ? ["error", "False alarm"] : finishing ? ["pending", "Finishing"] : ["ok", "Correct"];
  if (hit) return ["ok", "Detected"];
  if (finishing) return ["pending", "Finishing"];
  return evs.length ? ["pending", "Wrong category"] : ["error", "Missed"];
}

/** True for GRACE_MS after `done` turns true while this Verdict is mounted; a clip that had already ended when the page
 *  loaded is final at once (reload, coming back from another tab). Re-renders once when the window runs out. */
function useFinishing(done: boolean) {
  const [s, setS] = useState({ done, at: 0 });               // at = when this mount saw done turn true
  if (s.done !== done) setS({ done, at: done ? Date.now() : 0 });   // derived state, set during render
  const [, expire] = useState(0);
  useEffect(() => {
    if (!s.at) return;
    const t = setTimeout(() => expire((n) => n + 1), Math.max(0, s.at + GRACE_MS - Date.now()));
    return () => clearTimeout(t);
  }, [s.at]);
  return s.at > 0 && Date.now() - s.at < GRACE_MS;
}

const Head = ({ chip }: { chip?: ReactNode }) => (
  <div className="flex h-8 items-center justify-between gap-3">
    <h2 className="text-title-s-em text-on-surface">Verdict</h2>{chip}
  </div>
);

/** Empty Verdict of an empty slot (B-30). */
export function VerdictEmpty() {
  return (
    <Card radius="lg-plus" className="p-4">
      <Head />
      <p className="mt-2 text-body-l text-on-surface">No verdict yet</p>
      <p className="mt-1 text-body-s text-on-surface-variant">Play a labelled clip to see expected against detected, and the onset → alert time.</p>
    </Card>
  );
}

/** Clip Verdict (B-29..B-38): expected vs detected and the one large onset → alert number (D50). */
export function Verdict({ cam: c }: { cam: Camera }) {
  const { camStatus, camEvents } = useStore();
  const done = camStatus(c) === "ended";
  const finishing = useFinishing(done);
  const evs = camEvents(c.id).filter((e) => e.status !== "dismissed");
  const at = (e: Event) => { const ts = e.alert?.t_stored ?? e.start_ts; return ts && c.t_first ? `${(ts - c.t_first).toFixed(1)} s` : "—"; };
  const hit = evs.find((e) => e.category === c.label);
  const o2a = hit?.alert?.onset_to_alert_ms;
  const [variant, word] = stateOf(done, finishing, c, evs, hit);
  const hint = o2a != null ? `Alert at ${at(hit!)} in the clip, onset at ${c.onset_s} s`
    : hit ? `Alert at ${at(hit)} in the clip${c.onset_s == null ? "; no labelled onset" : ""}`
    : !c.label ? "Unlabelled clip: no onset to time from"
    : c.label === "normal" ? "Normal clip: no incident to time"
    : finishing ? "The model is still reviewing the last frames" : done ? "No matching alert" : "Waiting for the alert";
  const top = hit ?? evs[evs.length - 1];
  return (
    <Card as="section" radius="lg-plus" aria-label={`Verdict for ${c.name}`} className="@container flex flex-col gap-4 p-4">
      <Head chip={<StatusChip variant={variant}>{word}</StatusChip>} />

      <div className="flex items-center gap-4">
        <Shape name="cookie9" size={56} className="text-primary-container">
          <Icon name="timer" size={28} className="text-on-primary-container" />
        </Shape>
        <div className="min-w-0">
          <div className="text-label-l text-on-surface-variant">Onset → alert</div>
          <div className="text-display-s-em text-on-surface">{o2a != null ? ms(o2a) : "—"}</div>
        </div>
      </div>
      <p className="-mt-2 text-body-m text-on-surface-variant">{hint}</p>

      <Divider />

      <dl className="grid grid-cols-1 gap-4 @xs:grid-cols-2">
        <div className="min-w-0">
          <dt className="text-label-m text-on-surface-variant">Expected</dt>
          <dd className="mt-1 text-body-l text-on-surface">{c.label ? title(c.label) : "No label"}</dd>
          <dd className="font-mono text-body-s text-on-surface-variant">{c.onset_s != null ? `onset ${c.onset_s} s` : "no onset"}</dd>
        </div>
        <div className="min-w-0">
          <dt className="text-label-m text-on-surface-variant">Detected</dt>
          {evs.length ? evs.slice(-3).map((e) => (
            <dd key={e.id} className="mt-1 flex min-w-0 items-center gap-2">
              <Dot tone={sevTone(e.severity)} size={8} />
              <span className="truncate text-body-l text-on-surface">{title(e.category)}</span>
              <span className="ml-auto whitespace-nowrap font-mono text-body-s text-on-surface-variant">{pc(e.alert?.confidence ?? e.peak_confidence)} · {at(e)}</span>
            </dd>
          )) : <dd className="mt-1 text-body-l text-on-surface-variant">{done && !finishing ? "No incidents" : "Nothing yet"}</dd>}
        </div>
      </dl>

      {top && (top.summary
        ? <p className="rounded-md bg-surface-container-high px-3 py-2 text-body-m text-on-surface">{top.summary}</p>
        : <div aria-busy="true" className="rounded-md bg-surface-container-high px-3 py-3"><SkeletonLines lines={2} /></div>)}

      <div className="truncate font-mono text-body-s text-on-surface-variant">{`${c.name} · played once`}</div>
    </Card>
  );
}
