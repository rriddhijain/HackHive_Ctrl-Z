import type { ReactNode } from "react";

/** A Pipeline section surface (surface-container-low) with a title-s label and an optional right-hand note. */
export function Section({ label, note, children, className = "", busy }: {
  label: string; note?: ReactNode; children: ReactNode; className?: string; busy?: boolean;
}) {
  return (
    <section aria-label={label} aria-busy={busy || undefined} className={`rounded-xl bg-surface-container-low p-5 xl:p-6 ${className}`}>
      <div className="mb-4 flex items-baseline justify-between gap-4">
        <h2 className="text-title-s-em text-on-surface">{label}</h2>
        {note && <span className="truncate font-mono text-body-s text-on-surface-variant">{note}</span>}
      </div>
      {children}
    </section>
  );
}
