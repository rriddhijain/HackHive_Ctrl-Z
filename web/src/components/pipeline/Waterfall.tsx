import { EmptyState } from "@/components/m3";
import { ms } from "@/lib/format";
import type { Trace } from "@/lib/types";
import { Section } from "./Section";

const ROW = "grid grid-cols-[112px_minmax(0,1fr)_72px] items-center gap-3 sm:grid-cols-[168px_minmax(0,1fr)_88px] sm:gap-4";
const KEY = "1st token → category";

/** B-81: one bar per stage on a shared time axis (offset by the ms before it), the category stage emphasised. */
export function Waterfall({ t }: { t?: Trace }) {
  const total = (t?.stages ?? []).reduce((a, s) => a + s.ms, 0);
  let acc = 0;
  return (
    <Section label="Trace" note={t ? `${ms(total)} total` : undefined}>
      {t ? (
        <div role="list" aria-label="Trace stages">
          {t.stages.map((s) => {
            const left = total ? (acc / total) * 100 : 0, w = total ? Math.max((s.ms / total) * 100, 0.75) : 0;
            acc += s.ms;
            const key = s.name === KEY;
            return (
              <div role="listitem" key={s.name} className={`${ROW} h-8`}>
                <span className={`truncate ${key ? "text-body-m-em text-on-surface" : "text-body-m text-on-surface-variant"}`}>{s.name}</span>
                <div className="relative h-2.5 rounded-full bg-surface-container-highest">
                  <div style={{ left: `${left}%`, width: `${w}%` }}
                    className={`absolute inset-y-0 rounded-full ${key ? "bg-primary" : "bg-secondary"}`} />
                </div>
                <span className={`whitespace-nowrap text-right font-mono text-body-m ${key ? "text-on-surface" : "text-on-surface-variant"}`}>{ms(s.ms)}</span>
              </div>
            );
          })}
          <div className={`${ROW} mt-2`} aria-hidden="true">
            <span />
            <div className="flex justify-between border-t border-outline-variant pt-1.5 font-mono text-label-s text-on-surface-variant">
              <span>0</span><span>{ms(total)}</span>
            </div>
            <span />
          </div>
        </div>
      ) : (
        <EmptyState compact icon="hourglass_empty" shape="cookie12" title="Waiting for the first model call"
          body="The gate wakes the model on motion; baselines run when the scene changes." />
      )}
    </Section>
  );
}
