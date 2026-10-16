import { Card, DataTable, Dot, EmptyState, StatTile, StatusChip, type Column } from "@/components/m3";
import { ist, ms, name, v } from "@/lib/format";
import type { Report } from "@/lib/types";
import { Caption, Section } from "./Section";

type Acc = NonNullable<Report["accuracy"]>;
type ClipRow = Acc["clips"][number];

const p = (x: number | null | undefined) => (x == null ? "—" : `${Math.round(x * 100)}%`);
const pair = (x: [number | null, number | null] | null | undefined) => (x?.[0] == null ? "—" : `${ms(x[0])} / ${ms(x[1])}`);

/** B-89: Clip · Label · Detected · Onset→alert; row tooltip = the clip summary. */
const COLUMNS: Column<ClipRow>[] = [
  { key: "clip", header: "Clip", width: "38%", mono: true, render: (c) => c.clip },
  { key: "label", header: "Label", render: (c) => name(c.label) },
  {
    key: "pred", header: "Detected", render: (c) => {
      const ok = c.label === c.pred;
      return (
        <span className="inline-flex items-center gap-2">
          <Dot tone={ok ? "ok" : "critical"} size={8} />
          <span className={ok ? "text-on-surface" : "text-critical-text"}>{name(c.pred)}</span>
        </span>
      );
    },
  },
  { key: "onset", header: "Onset→alert", align: "right", width: "128px", render: (c) => (c.onset_to_alert_ms ? ms(+c.onset_to_alert_ms) : "—") },
];

/** B-86…B-90: the newest dev-set pass. */
export function AccuracySection({ a }: { a: Report["accuracy"] }) {
  return (
    <Section title="Accuracy · dev set" aside={a && <StatusChip variant="mono">{a.tag} · {ist(a.run_at)} IST</StatusChip>}>
      {!a ? (
        <EmptyState icon="monitoring" title="No dev-set run yet" body={<>Run: <span className="font-mono">uv run python -m bench.ab --dev --tag NAME</span></>} />
      ) : <AccuracyBody a={a} />}
    </Section>
  );
}

function AccuracyBody({ a }: { a: Acc }) {
  const errors = Object.entries(a.errors ?? {});
  return (
    <>
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <StatTile label="Clips right" value={`${a.right} / ${a.n}`} icon="check_circle" />
        <StatTile label="Incident recall" value={p(a.incident_recall)} icon="radar" />
        <StatTile label="Incident precision" value={p(a.incident_precision)} icon="target" />
        <StatTile label="False alarms on normal footage" value={v(a.false_alarms ?? a.false_alarms_normal)} icon="report_off" />
        <StatTile label="Onset → alert p50 / p95" value={pair(a.onset_to_alert_p50_p95)} icon="timer" shape="pill" tone="latency" />
        <StatTile label="Trigger → alert p50 / p95" value={pair(a.trigger_to_alert_p50_p95)} icon="bolt" shape="pill" tone="latency" />
        <StatTile label="Onset → alert, clip starts mid-incident" value={pair(a.onset_to_alert_mid_start_p50_p95)} icon="hourglass_bottom" shape="pill" tone="latency" />
        <StatTile label="GPU duty, mean" value={p(a.gpu_duty_mean)} icon="memory" />
      </div>
      <Caption>
        Each clip played once, alone, at real-time speed. Onset → alert over {a.onset_to_alert_n} clips whose incident starts after the
        first 2 s; {a.onset_to_alert_mid_start_n} clips that start mid-incident also time the buffer filling and are shown apart. A clip is
        judged on its alerts from 1 s before the incident; an earlier alert, or any alert on a normal clip, is a false alarm. Thresholds and
        prompts were tuned on these clips, so this is a training-set result; the test split is scored separately (REPORT.md).
      </Caption>
      <div className="mt-6 grid items-start gap-4 xl:grid-cols-12">
        <Card radius="lg-plus" className={`overflow-hidden py-2 ${errors.length ? "xl:col-span-8" : "xl:col-span-12"}`}>
          <DataTable aria-label="Per-clip results" columns={COLUMNS} rows={a.clips} rowKey={(c) => c.clip} rowTitle={(c) => c.summary} maxHeight={528} />
        </Card>
        {errors.length > 0 && (
          <Card radius="lg-plus" className="p-5 xl:col-span-4">
            <h3 className="text-title-s text-on-surface-variant">Errors by confusion pair</h3>
            <ul className="mt-3 flex flex-col gap-3">
              {errors.map(([k, list]) => (
                <li key={k} className="text-body-m">
                  <span className="font-mono text-critical-text">{k}</span>{" "}
                  <span className="text-on-surface-variant">· {list.map((x) => x.split(" ")[0]).join(", ")}</span>
                </li>
              ))}
            </ul>
          </Card>
        )}
      </div>
    </>
  );
}
