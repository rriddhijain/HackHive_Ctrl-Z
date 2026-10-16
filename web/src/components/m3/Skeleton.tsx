export interface SkeletonProps {
  /** Size and placement (h-3 w-2/3, aspect-video …). */
  className?: string;
  /** Radius of what it stands for: full for text lines (default), lg for tiles, sm for thumbnails. */
  radius?: "none" | "sm" | "md" | "lg" | "lg-plus" | "xl" | "full";
}

const R = { none: "rounded-none", sm: "rounded-sm", md: "rounded-md", lg: "rounded-lg", "lg-plus": "rounded-lg-plus", xl: "rounded-xl", full: "rounded-full" };

/** Shimmering placeholder (DESIGN §5.20); the region around it carries aria-busy. Static under reduced motion. */
export function Skeleton({ className = "h-3 w-full", radius = "full" }: SkeletonProps) {
  return <div aria-hidden="true" className={`hh-skeleton ${R[radius]} ${className}`} />;
}

/** N text lines (12 px tall, 8 px gaps), last ones shorter: the summary placeholder of B-37 / B-56. */
export function SkeletonLines({ lines = 2, className = "" }: { lines?: number; className?: string }) {
  const w = ["w-full", "w-2/3", "w-1/2", "w-4/5"];
  return (
    <div aria-hidden="true" className={`flex flex-col gap-2 ${className}`}>
      {Array.from({ length: lines }, (_, i) => <Skeleton key={i} className={`h-3 ${i === 0 ? "w-full" : w[i % w.length]}`} />)}
    </div>
  );
}
