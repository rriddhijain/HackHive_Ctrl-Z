import { Skeleton, StatTile } from "@/components/m3";
import { ms, v } from "@/lib/format";
import type { Metrics } from "@/lib/types";
import { Section } from "./Section";

type Row = [label: string, value: string, tip?: string, bad?: boolean];

/** B-84 rows: labels, values and tooltips verbatim; VLM errors > 0 and store → card p95 > 100 in the error style. */
function rows(m: Metrics): Row[] {
  const x = m.vlm ?? {}, o2a = m.latency?.onset_to_alert_ms, s2c = m.latency?.store_to_card_ms;
  return [
    ["GPU duty (60 s)", v(x.gpu_duty_pct, "%"), "Share of the last 60 s the model was busy. Target ≤ 60 % average with 3 cameras."],
    ["Onset → alert", o2a?.n ? `${ms(o2a.last)} · p50 ${o2a.p50}` : "—",
      "Labelled incident onset in the clip → alert (§12). Only for labelled clips played once (uploads, bench/labels.csv); live onset is measured from 240 fps phone video."],
    ["Model time-to-alert p95", ms(x.alert_p95_ms), "Newest frame captured → category known, p95 over all calls. Never quoted alone (D50)."],
    ["VLM call p50 / p95", `${v(x.p50_ms)} / ${v(x.p95_ms)} ms`],
    ["Store → card p95", s2c?.n ? `${ms(s2c.p95)} · n ${s2c.n}` : "—",
      "Event row stored → card painted in this browser; budget ≤ 100 ms. Valid only when the browser runs on the server machine (it compares the two clocks); readings from other devices are ignored.",
      (s2c?.p95 ?? 0) > 100],
    ["Queue", v(x.queue_depth)],
    ["Calls", v(x.calls_total)],
    ["Preempted", v(x.preemptions)],
    ["Baselines skipped", v(x.baselines_skipped), "Baseline calls skipped because the scene had not changed (D42)."],
    ["Vetoes", v(x.vetoes), "Detector cross-check vetoes (E-7)."],
    ["VLM errors", v(x.errors), "The server log prints each [vlm_error] line.", (x.errors ?? 0) > 0],
    ["Memory", v(m.system?.mem_used_pct, "%")],
  ];
}

const GRID = "grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4 xl:gap-4";

/** B-84 System grid; shown with or without cameras. Skeleton tiles until the first metrics. */
export function SystemGrid({ m }: { m: Metrics | null }) {
  return (
    <Section label="System" busy={!m}>
      <div className={GRID}>
        {m ? rows(m).map(([label, value, tip, bad]) => (
          <StatTile key={label} label={label} value={value} tooltip={tip} critical={bad} />
        )) : Array.from({ length: 12 }, (_, i) => <Skeleton key={i} radius="lg-plus" className="h-32 w-full" />)}
      </div>
    </Section>
  );
}
