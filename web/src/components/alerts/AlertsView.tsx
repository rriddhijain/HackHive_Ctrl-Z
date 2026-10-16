"use client";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";
import { Button, Chip, EmptyState, List, PageHeader, Select, Skeleton, SkeletonLines, TextField } from "@/components/m3";
import { Page } from "@/components/shell";
import { name } from "@/lib/format";
import { useEvent, useStore } from "@/lib/store";
import type { Event } from "@/lib/types";
import { AlertCard } from "./AlertCard";
import { AlertReport, ReportEmpty, ReportSkeleton } from "./AlertReport";

type Filter = "all" | "open" | "critical" | "high" | "medium";
const FILTERS: { value: Filter; label: string }[] = [
  { value: "all", label: "All" }, { value: "open", label: "Open" },
  { value: "critical", label: "Critical" }, { value: "high", label: "High" }, { value: "medium", label: "Medium" },
];
const pass = (f: Filter, e: Event) => f === "all" || (f === "open" ? e.status === "open" : e.severity === f);

function CardSkeleton() {
  return (
    <li className="rounded-xs bg-surface-container px-4 py-3 pl-6">
      <div className="flex gap-4">
        <Skeleton className="aspect-video w-24 shrink-0" radius="sm" />
        <div className="flex-1"><Skeleton className="h-4 w-1/2" /><Skeleton className="mt-2 h-3 w-1/3" /></div>
      </div>
      <SkeletonLines lines={2} className="mt-3" />
    </li>
  );
}

/** Alerts tab (DESIGN §6.3): the filterable list (B-51…B-58) beside the selected alert's report (§4.6). */
export function AlertsView() {
  const router = useRouter();
  const id = Number(useSearchParams().get("id")) || null;
  const { feed: rows, evLoad, camName } = useStore();   // B-5: non-dismissed, id desc, first 50
  const { event, state } = useEvent(id);

  const [filter, setFilter] = useState<Filter>("all");
  const [cam, setCam] = useState("");
  const [q, setQ] = useState("");
  const cams = useMemo(() => {
    const seen = new Map<string, string>();
    for (const e of rows) if (!seen.has(e.camera_id)) seen.set(e.camera_id, camName(e));
    return [...seen].sort((a, b) => a[1].localeCompare(b[1]));
  }, [rows, camName]);
  const shown = useMemo(() => {
    const s = q.trim().toLowerCase();
    return rows.filter((e) => pass(filter, e) && (!cam || e.camera_id === cam)
      && (!s || [name(e.category), camName(e), e.summary ?? ""].some((t) => t.toLowerCase().includes(s))));
  }, [rows, filter, cam, q, camName]);

  const ok = evLoad === "ok";
  const failed = evLoad === "error";
  const open = (n: number) => router.push(`/alerts/?id=${n}`);
  const close = () => router.push("/alerts/");
  const clear = () => { setFilter("all"); setCam(""); setQ(""); };

  const report = state === "ok" && event ? <AlertReport key={event.id} event={event} onClose={close} />
    : state === "loading" ? <ReportSkeleton />
    : <ReportEmpty id={state === "missing" || state === "error" ? id ?? undefined : undefined} error={state === "error"} onClose={close} />;

  // Nothing to list and nothing asked for: one centred state instead of two panes (DESIGN §6.3).
  if (ok && !rows.length && id == null) {
    return (
      <Page className="pb-10">
        <PageHeader title="Alerts" />
        <div className="rounded-xl-plus bg-surface-container-low">
          <EmptyState icon="check_circle" title="No alerts" body="Incidents appear here the moment the model confirms one." />
        </div>
      </Page>
    );
  }

  return (
    <Page className="pb-10">
      <PageHeader title="Alerts" />
      <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
        {/* Below lg one pane at a time: the report replaces the list while an alert is selected. */}
        <section aria-label="Alert list" className={`min-w-0 ${id != null ? "hidden lg:block" : ""}`}>
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex flex-wrap gap-2" role="group" aria-label="Filter alerts">
              {FILTERS.map((f) => (
                <Chip key={f.value} type="filter" selected={filter === f.value} onClick={() => setFilter(f.value)}>{f.label}</Chip>
              ))}
            </div>
            {ok && <span className="ml-auto text-label-l text-on-surface-variant">{shown.length} of {rows.length}</span>}
          </div>
          <div className="mt-3 grid grid-cols-1 gap-3 xl:grid-cols-2">
            <Select label="Camera" value={cam} onChange={(v) => setCam(v)}
              groups={[{ options: [{ value: "", label: "All cameras" }, ...cams.map(([v, label]) => ({ value: v, label }))] }]} />
            <TextField variant="outlined" label="Search" leadingIcon="search" value={q} onChange={setQ} placeholder="Category, camera or summary"
              trailing={q ? <Button variant="text" size="xs" onClick={() => setQ("")}>Clear</Button> : undefined} />
          </div>

          <div className="mt-4">
            {failed ? (
              <div className="rounded-xl bg-surface-container-low">
                <EmptyState tone="error" icon="error" title="Could not load alerts" body="Check the server is running, then reload the page." />
              </div>
            ) : !ok ? (
              <ul aria-busy="true" aria-label="Alerts" className="flex flex-col gap-0.5 overflow-hidden rounded-lg">
                {[0, 1, 2].map((i) => <CardSkeleton key={i} />)}
              </ul>
            ) : !rows.length ? (
              <div className="rounded-xl bg-surface-container-low">
                <EmptyState icon="check_circle" title="No alerts" body="Incidents appear here the moment the model confirms one." />
              </div>
            ) : !shown.length ? (
              <div className="rounded-xl bg-surface-container-low">
                <EmptyState icon="filter_alt_off" title="No matching alerts" body="Change the filters or clear the search."
                  action={<Button variant="tonal" icon="close" onClick={clear}>Clear filters</Button>} />
              </div>
            ) : (
              <List aria-label="Alerts" aria-live="polite">
                {shown.map((e) => <AlertCard key={e.id} event={e} selected={e.id === id} onOpen={open} />)}
              </List>
            )}
          </div>
        </section>

        <section aria-label="Alert report" className={`min-w-0 ${id == null ? "hidden lg:block" : ""} lg:sticky lg:top-20 lg:max-h-[calc(100dvh-6rem)] lg:overflow-y-auto lg:rounded-xl-plus`}>
          {report}
        </section>
      </div>
    </Page>
  );
}
