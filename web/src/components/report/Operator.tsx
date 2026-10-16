import { Button, StatTile } from "@/components/m3";
import { api } from "@/lib/api";
import { ms, v } from "@/lib/format";
import type { Report } from "@/lib/types";
import { Caption, Section } from "./Section";

/** B-91…B-93: live operator numbers since server start, and the labels export. */
export function OperatorSection({ op, lat }: { op: Report["operator"]; lat: Report["latency"] }) {
  const s2c = lat.store_to_card_ms;
  return (
    <Section title="Operator · since server start"
      aside={<Button variant="text" icon="download" href={api.feedbackCsv}>Export operator labels (CSV)</Button>}>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3 huge:grid-cols-6">
        <StatTile label="Events (real, not seeded)" value={v(op.events)} icon="notifications" shape="clover8" tone="operator" />
        <StatTile label="Marked false alarm" value={v(op.false_alarms)} icon="report_off" shape="clover8" tone="operator" />
        <StatTile label="Monitored camera-hours" value={op.camera_hours.toFixed(2)} icon="schedule" shape="clover8" tone="operator" />
        <StatTile label="False alarms / camera-hour" value={op.false_alarms_per_camera_hour == null ? "—" : String(op.false_alarms_per_camera_hour)}
          icon="speed" shape="clover8" tone="operator" />
        <StatTile label="Onset → alert p50 (live)" value={lat.onset_to_alert_ms?.n ? ms(lat.onset_to_alert_ms.p50) : "—"}
          icon="timer" shape="pill" tone="latency" />
        {/* Red over the 100 ms budget, as in Pipeline (B-80 store → card row). */}
        <StatTile label="Store → card p95" value={s2c?.n ? ms(s2c.p95) : "—"} critical={!!s2c?.n && (s2c.p95 ?? 0) > 100}
          icon="bolt" shape="pill" tone="latency" />
      </div>
      <Caption>
        Camera-hours run from each source's first to last observation; live rows reset when the server starts, the exported labels don't. A rate needs at least 3 camera-minutes; the target is ≤ 1 per camera-hour.
      </Caption>
    </Section>
  );
}
