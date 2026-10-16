"use client";
import { Fragment } from "react";
import { Icon, Shape, Skeleton, StatusChip, Tooltip } from "@/components/m3";
import { ist, ms, n } from "@/lib/format";
import type { ShapeName } from "@/lib/shapes";
import type { Camera, CamMetrics, Pctl, Trace } from "@/lib/types";

interface Node { label: string; value: string; unit: string; tip: string; icon: string; shape: ShapeName; key?: boolean }

/** B-80: the five nodes, values from metrics (Frame, YOLO) and this call's trace (Gate, VLM, Event). */
function nodes(t: Trace | undefined, cm: CamMetrics | undefined): Node[] {
  const st: Record<string, number> = Object.fromEntries((t?.stages ?? []).map((s) => [s.name, s.ms]));
  const a = st["prefill → 1st token"], b = st["1st token → category"];
  const vlm = a != null || b != null ? (a ?? 0) + (b ?? 0) : null;
  return [
    { label: "Frame", value: n(cm?.capture_fps), unit: "fps", tip: "Capture rate", icon: "frame_inspect", shape: "cookie9" },
    { label: "YOLO", value: n(cm?.yolo_ms_p50), unit: "ms p50", tip: "YOLO + ByteTrack per frame, p50", icon: "person_search", shape: "clover4" },
    { label: "Gate", value: n(st["capture → gate"]), unit: "ms", tip: "Frame captured → gate fired, this call (includes detection)", icon: "filter_alt", shape: "cookie6" },
    { label: "VLM", value: n(vlm), unit: "ms", tip: "Prefill + first token → category known, this call", icon: "neurology", shape: "sunny", key: true },
    { label: "Event", value: n(st["store (SQLite)"]), unit: "ms", tip: "Event row stored in SQLite, this call", icon: "notifications", shape: "cookie12" },
  ];
}

/** B-79 header + B-80 stepper: camera, time and trigger left, the Frame → category headline right, five nodes below. */
export function Hero({ cam, t, cm, o2a }: { cam: Camera; t?: Trace; cm?: CamMetrics; o2a?: Pctl }) {
  return (
    <section aria-label="Model call" className="rounded-xl-plus bg-surface-container-low p-5 xl:p-6">
      <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-4">
        <div className="min-w-0">
          <div className="truncate text-title-l-em text-on-surface">{cam.name}</div>
          <div className="mt-1 font-mono text-body-m text-on-surface-variant">{cam.id} · {t ? ist(t.ts) : "—"}</div>
          {t && <StatusChip variant="mono" className="mt-3">{t.trigger}</StatusChip>}
        </div>
        <div className="shrink-0 text-right">
          <div className="text-label-l text-on-surface-variant">Frame → category</div>
          <div className="mt-1 text-display-s-em text-on-surface">{ms(t?.model_tta_ms)}</div>
          <Tooltip content="Never quote the model time alone (D50)">
            <span tabIndex={0} className="mt-1 inline-block rounded-xs font-mono text-body-m text-on-surface-variant">
              onset → alert p50 {o2a?.n ? ms(o2a.p50) : "—"}
            </span>
          </Tooltip>
        </div>
      </div>

      <ol aria-label="Pipeline stages" className="mt-6 flex flex-col items-stretch gap-2 lg:flex-row lg:items-center">
        {nodes(t, cm).map((x, i) => (
          <Fragment key={x.label}>
            {i > 0 && (
              <li aria-hidden="true" className="flex shrink-0 justify-center text-outline">
                <Icon name="arrow_forward" size={24} className="rotate-90 lg:rotate-0" />
              </li>
            )}
            <li className="min-w-0 lg:flex-1">
              <Tooltip content={x.tip} className="w-full">
                <div tabIndex={0} className={`flex w-full items-center gap-4 rounded-lg-plus p-4 xl:p-5 ${x.key ? "bg-primary-container text-on-primary-container" : "bg-surface-container text-on-surface"}`}>
                  <Shape name={x.shape} size={44} className={x.key ? "text-primary" : "text-primary-fixed"}>
                    <Icon name={x.icon} size={22} className={x.key ? "text-on-primary" : "text-on-primary-fixed-variant"} />
                  </Shape>
                  <div className="min-w-0">
                    <div className={`text-label-l ${x.key ? "" : "text-on-surface-variant"}`}>{x.label}</div>
                    <div className="flex items-baseline gap-1.5 whitespace-nowrap">
                      <span className="text-headline-s-em">{x.value}</span>
                      <span className={`text-body-m ${x.key ? "" : "text-on-surface-variant"}`}>{x.unit}</span>
                    </div>
                  </div>
                </div>
              </Tooltip>
            </li>
          </Fragment>
        ))}
      </ol>
    </section>
  );
}

/** Loading placeholder for the hero before the first metrics arrive. */
export function HeroSkeleton() {
  return (
    <section aria-label="Model call" aria-busy className="rounded-xl-plus bg-surface-container-low p-5 xl:p-6">
      <div className="flex items-start justify-between gap-8">
        <div className="flex flex-col gap-3"><Skeleton className="h-5 w-48" /><Skeleton className="h-3 w-32" /></div>
        <div className="flex flex-col items-end gap-3"><Skeleton className="h-3 w-28" /><Skeleton className="h-9 w-40" /></div>
      </div>
      <div className="mt-6 grid gap-4 lg:grid-cols-5">
        {Array.from({ length: 5 }, (_, i) => <Skeleton key={i} radius="lg-plus" className="h-20 w-full" />)}
      </div>
    </section>
  );
}
