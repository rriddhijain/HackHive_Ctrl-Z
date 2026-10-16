"use client";
import { useStore } from "@/lib/store";
import { FeedTile } from "./FeedTile";

/** Sources with slot null (only from a no-slot start while all 3 slots were full): visible and stoppable (§4.3). */
export function OtherSources({ className = "" }: { className?: string }) {
  const { overflow } = useStore();
  if (!overflow.length) return null;
  return (
    <section aria-label="Other sources" className={className}>
      <h2 className="mb-3 text-title-s-em text-on-surface">Other sources</h2>
      <div className="flex flex-wrap gap-4">{overflow.map((c) => <FeedTile key={c.id} cam={c} className="w-60" />)}</div>
    </section>
  );
}
