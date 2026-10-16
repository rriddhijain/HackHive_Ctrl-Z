export interface LoadingIndicatorProps {
  /** Container size in px. */
  size?: number;
  /** Contained: a primary-container circle behind the spinner. */
  contained?: boolean;
  "aria-label": string;
  className?: string;
}

/** Plain circular progress (basic motion, captain 19:15: no shape morph): a 3/4 arc turning once a second. */
export function LoadingIndicator({ size = 48, contained, className = "", ...aria }: LoadingIndicatorProps) {
  const s = Math.round(size * (contained ? 0.5 : 0.75));
  return (
    <span role="progressbar" aria-label={aria["aria-label"]} style={{ width: size, height: size }}
      className={`inline-grid shrink-0 place-items-center rounded-full ${contained ? "bg-primary-container text-on-primary-container" : "text-primary"} ${className}`}>
      <svg width={s} height={s} viewBox="0 0 24 24" aria-hidden="true" className="hh-spin">
        <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeDasharray="47 63" />
      </svg>
    </span>
  );
}
