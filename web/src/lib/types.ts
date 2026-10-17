// Wire types (SPEC §9, docs/ui/CONTRACT.md §1-§2). Every timestamp is epoch seconds.

export type Mode = "clips" | "live";
export type Slot = 1 | 2 | 3;
export const SLOTS: readonly Slot[] = [1, 2, 3];
export type Severity = "critical" | "high" | "medium";
export type EventStatus = "open" | "closed" | "acknowledged" | "dismissed";
export type CamStatus = "connecting" | "live" | "reconnecting" | "down" | "ended" | "stopped";

/** E-1 row. `slot` is null only for a source started without a slot while all three were full. */
export interface Camera {
  id: string;
  name: string;
  source_type: "file" | "webcam" | "stream";
  source: string | number;
  status: CamStatus | string;
  fps: number | null;
  has_door_zone: boolean;
  loop: boolean;
  t_first: number | null;
  label: string | null;
  onset_s: number | null;
  slot: Slot | null;
}

/** E-3 row. */
export interface Clip { path: string; name: string; folder: string; label: string | null; onset_s: number | null }

/** E-6 row. An iPhone is named exactly `iPhone (live)`; string sources are preset stream URLs. */
export interface Device { source: number | string; name: string }

/** SSE `alert` (§2). Kept on the event under `alert` forever: that key marks a live alert. */
export interface AlertMsg {
  event_id: number;
  camera_id: string;
  category: string;
  severity: Severity;
  confidence: number;
  rating: "High" | "Medium" | "Low";
  top3: [string, number][];
  trigger_to_alert_ms: number | null;
  t_stored: number;
  onset_to_alert_ms: number | null;
}

/** Event row (E-10, SSE). Store entries are partial merges, so most fields may be missing. */
export interface Event {
  id: number;
  camera_id: string;
  category: string;
  subtype?: string | null;
  severity: Severity | string;
  start_ts?: number | null;
  end_ts?: number | null;
  peak_confidence?: number | null;
  summary?: string | null;
  keyframe_paths?: string[] | null;
  track_ids?: number[] | null;
  status: EventStatus | string;
  dismiss_reason?: null | "relook" | "operator";
  n_obs?: number;
  time_to_alert_ms?: number | null;
  latency_ms?: number | null;
  seeded?: 0 | 1 | boolean;
  camera_name?: string;
  alert?: AlertMsg;
}

/** SPEC §7.1; the UI reads only `probs`. */
export interface Observation { id?: number; event_id?: number; ts?: number; probs?: Record<string, number> | null; [k: string]: unknown }
export type EventDetail = Event & { observations: Observation[] };

export interface Pctl { last: number | null; p50: number | null; p95: number | null; n: number }
export interface CamMetrics {
  capture_fps: number | null;
  det_fps: number | null;
  yolo_ms_p50: number | null;
  keep_up: number | null;
  status: CamStatus | string;
  people: number | null;
  now: { text: string; ts: number; source: "model" | "detector" } | null;
}
/** SSE `metrics` (§9.1), replaced whole every second. */
export interface Metrics {
  mode: Mode;
  cameras: Record<string, CamMetrics>;
  vlm: {
    model: string | null; p50_ms: number | null; p95_ms: number | null; alert_p95_ms: number | null;
    queue_depth: number | null; calls_total: number | null; gate_yield_pct: number | null; cache_hit_tokens: number | null;
    preemptions: number | null; errors: number | null; gpu_duty_pct: number | null; baselines_skipped: number | null; vetoes: number | null;
  };
  latency: { onset_to_alert_ms: Pctl; store_to_card_ms: Pctl };
  system: { mem_used_pct: number | null; uptime_s: number | null };
  /** ESP32 guard console (D89); null when switched off in config.yaml. */
  console?: {
    connected: boolean; port: string | null; timing: boolean; board_alarm: number | null;
    last: { event_id: number; category: string | null; ms: number; ts: number } | null;
  } | null;
}

/** SSE `trace`, newest per camera. Stage order: capture → gate, queue, prefill → 1st token, 1st token → category, category → done, store (SQLite). */
export interface Trace {
  camera_id: string;
  trigger: string;
  ts: number;
  stages: { name: string; ms: number }[];
  model_tta_ms: number | null;
  mosaic_url: string;
  hints: string | null;
  raw_json: string;
}

export interface ChatHow {
  mode: "template" | "model";
  read_by?: "rules" | "model";
  read_ms?: number;
  rows?: number;
  sentences?: number;
  dropped?: number;
  first_token_ms?: number;
  fallback?: "template";
  note?: string;
  digest?: boolean;
}
/** E-14 response. */
export interface ChatAnswer { answer: string; events: Event[]; filters?: unknown; as_of: number; latency_ms: number; how: ChatHow }
/** E-15 response. */
export interface Digest {
  from: number; to: number; camera: string | null; headline: string; narrative: string;
  incidents: { id: number; line: string; status: string; severity: string; seeded: number | boolean }[];
  follow_up: number[];
  activity: { camera: string; notes: string[]; peak_people: number | null }[];
  events: Event[];
  how: ChatHow;
  as_of: number;
  latency_ms: number;
}
/** One Ask log entry (B-71, B-76). */
export interface ChatEntry {
  question: string;
  answer: string;
  events: Event[];
  how?: ChatHow;
  as_of?: number;
  latency_ms?: number;
  error?: boolean;
}

/** E-16 response. Clip fields are CSV strings. */
export interface Report {
  accuracy: null | {
    tag: string; run_at: number; n: number; right: number; macro_f1: number | null;
    incident_recall: number | null; incident_precision: number | null; false_alarms_normal: number | null; false_alarms?: number | null;
    onset_to_alert_p50_p95: [number | null, number | null] | null; onset_to_alert_n: number;
    onset_to_alert_mid_start_p50_p95: [number | null, number | null] | null; onset_to_alert_mid_start_n: number;
    trigger_to_alert_p50_p95: [number | null, number | null] | null; gpu_duty_mean?: number | null;
    errors: Record<string, string[]>;
    clips: { clip: string; label: string; pred: string; confidence: string; onset_to_alert_ms: string; trigger_to_alert_ms: string; summary: string }[];
  };
  latency: Metrics["latency"] & { trigger_to_alert_p95_ms?: number | null };
  operator: { events: number; false_alarms: number; camera_hours: number; false_alarms_per_camera_hour: number | null; by_category: Record<string, unknown> };
}

/** E-4, E-5, E-7 response. */
export interface Started { id: string; name: string; status: string; slot: Slot | null }
