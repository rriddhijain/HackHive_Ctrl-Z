"use client";
import { Skeleton } from "@/components/m3";
import { name, pc } from "@/lib/format";
import type { Top3 } from "./useTop3";

const SEG = ["bg-on-surface", "bg-on-surface/60", "bg-on-surface/32"];

/** B-50: a 6 px segmented bar in neutral tones (never severity) and three `${pc} ${name}` labels, the first emphasised. */
export function Top3Bar({ top3, className = "" }: { top3: Top3 | null | false; className?: string }) {
  if (top3 === false) return null;
  if (!top3) return <Skeleton className={`h-1.5 w-full ${className}`} />;
  return (
    <div className={className}>
      <div className="flex h-1.5 gap-0.5 overflow-hidden rounded-full bg-surface-container-highest">
        {top3.map(([k, c], i) => (
          <div key={k} style={{ width: `${c * 100}%` }} className={`h-full rounded-full ${SEG[i]}`} />
        ))}
      </div>
      <div className="mt-1.5 grid grid-cols-3 gap-3 text-body-s text-on-surface-variant">
        {top3.map(([k, c], i) => <span key={k} className={`truncate ${i ? "" : "text-body-s-em text-on-surface"}`}>{pc(c)} {name(k)}</span>)}
      </div>
    </div>
  );
}
