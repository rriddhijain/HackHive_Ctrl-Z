import { pretty } from "@/lib/format";
import type { Trace } from "@/lib/types";
import { Section } from "./Section";

const SUB = "mb-2 text-label-l text-on-surface-variant";

/** B-82: what the model saw (letterboxed mosaic, never stretched), the hints and what it said (pretty raw JSON). */
export function ModelInput({ t }: { t: Trace }) {
  return (
    <Section label="Model input" note="mosaic · letterboxed">
      <div className="grid gap-5 xl:grid-cols-[minmax(0,5fr)_minmax(0,3fr)_minmax(0,4fr)] xl:gap-6">
        <img src={t.mosaic_url} alt="Mosaic of recent frames sent to the VLM"
          className="block aspect-video w-full rounded-lg bg-black object-contain" />
        <div className="min-w-0">
          <div className={SUB}>Hints</div>
          <p className="whitespace-pre-wrap wrap-break-word text-body-m text-on-surface">{t.hints || "None"}</p>
        </div>
        <div className="min-w-0">
          <div className={SUB}>Raw VLM output</div>
          <pre tabIndex={0} aria-label="Raw VLM output"
            className="max-h-54 overflow-auto whitespace-pre-wrap wrap-break-word rounded-md bg-surface-container-highest p-3 font-mono text-body-s text-on-surface-variant">
            {pretty(t.raw_json)}
          </pre>
        </div>
      </div>
    </Section>
  );
}
