"use client";
// Report (FR-20, CONTRACT §3.15): the newest dev-set pass plus live operator numbers. Every figure is measured.
import { useEffect, useState } from "react";
import { EmptyState, PageHeader } from "@/components/m3";
import { AccuracySection } from "@/components/report/Accuracy";
import { OperatorSection } from "@/components/report/Operator";
import { ReportSkeleton } from "@/components/report/Section";
import { Page } from "@/components/shell";
import { api } from "@/lib/api";
import type { Report } from "@/lib/types";

export default function ReportPage() {
  const [r, setR] = useState<Report | null | false>(null);   // null loading · false error
  useEffect(() => {   // B-85: on mount and every 10 s while this tab is shown
    let live = true;
    const load = () => api.report().then((x) => live && setR(x)).catch(() => live && setR(false));
    load();
    const t = setInterval(load, 10000);
    return () => { live = false; clearInterval(t); };
  }, []);

  return (
    <Page className="pb-12">
      <PageHeader title="Report" />
      {r === null ? <ReportSkeleton />
        : r === false ? (
          <div className="rounded-xl bg-surface-container-low">
            <EmptyState icon="error" tone="error" title="Could not load the report" body="Check the server is running." />
          </div>
        ) : (
          <div className="flex flex-col gap-8">
            <AccuracySection a={r.accuracy} />
            <OperatorSection op={r.operator} lat={r.latency} />
          </div>
        )}
    </Page>
  );
}
