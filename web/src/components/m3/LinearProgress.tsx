export interface LinearProgressProps {
  /** 0..1 for determinate; omit for indeterminate. */
  value?: number;
  "aria-label": string;
  className?: string;
}

/** M3 linear progress (DESIGN §5.17): 4 px track, 4 px gap, stop dot. Flat (no wavy, basic motion). */
export function LinearProgress({ value, className = "", ...aria }: LinearProgressProps) {
  const det = value != null;
  const pct = det ? Math.max(0, Math.min(1, value)) * 100 : 0;
  return (
    <div role="progressbar" aria-label={aria["aria-label"]} aria-valuemin={det ? 0 : undefined} aria-valuemax={det ? 100 : undefined}
      aria-valuenow={det ? Math.round(pct) : undefined} className={`relative flex h-2.5 w-full items-center ${className}`}>
      {det ? (
        <>
          <div className="h-1 rounded-full bg-primary" style={{ width: `${pct}%` }} />
          <div className="ml-1 h-1 flex-1 rounded-full bg-secondary-container" />
          <span className="absolute right-0 size-1 rounded-full bg-primary" />
        </>
      ) : (
        <div className="relative h-1 w-full overflow-hidden rounded-full bg-secondary-container">
          <div className="hh-indet absolute inset-y-0 w-2/5 rounded-full bg-primary" />
        </div>
      )}
    </div>
  );
}
