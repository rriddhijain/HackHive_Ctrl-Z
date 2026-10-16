"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Event } from "@/lib/types";

export type Top3 = [string, number][];

// One fetch per (id, n_obs) for the page's life, shared by every card, report and revisit of the tab.
// ponytail: unbounded map, fine for a session's few hundred events; add an LRU if pages stay open for days.
const cache = new Map<string, Promise<Top3 | false>>();
const peak = (e: Event): Promise<Top3 | false> => {
  const k = `${e.id}:${e.n_obs ?? ""}`;
  let p = cache.get(k);
  if (!p) {
    p = api.event(e.id).then((d) => {
      const o = d.observations?.filter((x) => x.probs).sort((a, b) => (b.probs![e.category] ?? 0) - (a.probs![e.category] ?? 0))[0];
      return o?.probs ? (Object.entries(o.probs).sort((a, b) => b[1] - a[1]).slice(0, 3) as Top3) : false;
    }, () => { cache.delete(k); return false as const; });
    cache.set(k, p);
  }
  return p;
};

/**
 * B-49: a live alert's top-3 from its SSE message; otherwise the event's peak observation (highest probs[category]),
 * refetched when id or n_obs changes. null = pending (skeleton bar), false = nothing to show.
 */
export function useTop3(e: Event): Top3 | null | false {
  const [t3, setT3] = useState<{ k: string; v: Top3 | false } | null>(null);
  const k = `${e.id}:${e.n_obs ?? ""}`;
  useEffect(() => {
    if (e.alert) return;
    let alive = true;
    void peak(e).then((v) => { if (alive) setT3({ k, v }); });
    return () => { alive = false; };
  }, [k]); // eslint-disable-line react-hooks/exhaustive-deps
  return e.alert?.top3 ?? (t3 ? t3.v : null);
}
