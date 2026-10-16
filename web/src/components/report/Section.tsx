import type { ReactNode } from "react";
import { Skeleton } from "@/components/m3";

/** A Report section (DESIGN §6.6): surface-container-low, xl radius, title row with an optional right side. */
export function Section({ title, aside, children }: { title: string; aside?: ReactNode; children: ReactNode }) {
  return (
    <section className="rounded-xl bg-surface-container-low p-4 xl:p-6">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <h2 className="text-title-l text-on-surface">{title}</h2>
        {aside}
      </div>
      {children}
    </section>
  );
}

/** Caption under a tile grid (B-88, B-92). */
export function Caption({ children }: { children: ReactNode }) {
  return <p className="mt-4 max-w-[120ch] text-body-s text-on-surface-variant">{children}</p>;
}

/** First load (B-85): the shape of both sections. */
export function ReportSkeleton() {
  const tiles = (k: number, cls: string) => (
    <div className={`grid grid-cols-2 gap-4 ${cls}`}>
      {Array.from({ length: k }, (_, i) => <Skeleton key={i} className="h-32" radius="lg-plus" />)}
    </div>
  );
  return (
    <div aria-busy="true" aria-label="Loading the report" className="flex flex-col gap-8">
      <div className="rounded-xl bg-surface-container-low p-4 xl:p-6">
        <Skeleton className="mb-4 h-6 w-48" />
        {tiles(8, "xl:grid-cols-4")}
        <Skeleton className="mt-4 h-64 w-full" radius="lg-plus" />
      </div>
      <div className="rounded-xl bg-surface-container-low p-4 xl:p-6">
        <Skeleton className="mb-4 h-6 w-56" />
        {tiles(6, "lg:grid-cols-3 huge:grid-cols-6")}
      </div>
    </div>
  );
}
