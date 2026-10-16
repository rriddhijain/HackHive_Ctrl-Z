// One typed function per endpoint the UI uses (CONTRACT §1). Same-origin relative URLs.
// Non-2xx rejects with ApiError carrying the server's `detail` as a string (422 arrays are stringified).
import type { Camera, ChatAnswer, Clip, Device, Digest, Event, EventDetail, Mode, Report, Slot, Started } from "./types";

/** D89: GET /api/notify. */
export interface NotifyStatus {
  enabled: boolean; channels: string[]; queued: number; dropped: number; cooldown_s: number; min_confidence: number;
  recent: { ts: number; event_id: number; channel: string; ok: boolean; ms: number; error: string | null }[];
}

export class ApiError extends Error {
  constructor(public status: number, public detail: string) { super(detail); }
}

/** FastAPI `detail` as display text: a string as is, a 422 array as its messages. */
export const detailText = (d: unknown): string =>
  typeof d === "string" ? d
    : Array.isArray(d) ? d.map((x) => (x && typeof x === "object" && "msg" in x ? String((x as { msg: unknown }).msg) : JSON.stringify(x))).join("; ")
    : d == null ? "" : JSON.stringify(d);

async function req<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, init);
  if (!r.ok) {
    let detail = r.statusText;
    try { detail = detailText((await r.json()).detail) || detail; } catch { /* not JSON */ }
    throw new ApiError(r.status, detail);
  }
  return r.json() as Promise<T>;
}
const json = (method: string, body?: unknown): RequestInit =>
  ({ method, headers: { "Content-Type": "application/json" }, body: body === undefined ? undefined : JSON.stringify(body) });

export const api = {
  /** E-1 */ cameras: () => req<Camera[]>("/api/cameras"),
  /** E-2: stops every source in either mode; history stays. */ setMode: (mode: Mode) => req<{ mode: Mode; switch_ms: number }>("/api/mode", json("POST", { mode })),
  /** E-3 */ clips: () => req<Clip[]>("/api/clips"),
  /** E-4: always send slot (no slot stops the other columns). */ playClip: (path: string, slot: Slot) => req<Started>("/api/clips/play", json("POST", { path, slot })),
  /** E-5: raw bytes body. */ upload: (file: File, slot: Slot) =>
    req<Started>(`/api/cameras/upload?name=${encodeURIComponent(file.name)}&slot=${slot}`, { method: "POST", body: file }),
  /** E-6 */ devices: () => req<Device[]>("/api/devices"),
  /** E-7 */ addSource: (source: number | string, name: string | null, slot: Slot) => req<Started>("/api/cameras", json("POST", { source, name, slot })),
  /** E-8 */ removeSource: (id: string) => req<{ id: string; removed: true }>(`/api/cameras/${id}`, { method: "DELETE" }),
  /** E-10 */ events: (limit = 50) => req<Event[]>(`/api/events?limit=${limit}`),
  /** E-11 */ event: (id: number) => req<EventDetail>(`/api/events/${id}`),
  /** E-12 */ ack: (id: number) => req<EventDetail>(`/api/events/${id}/ack`, { method: "POST" }),
  /** E-13 */ dismiss: (id: number) => req<EventDetail>(`/api/events/${id}/dismiss`, { method: "POST" }),
  /** E-14 */ chat: (session_id: string, question: string) => req<ChatAnswer>("/api/chat", json("POST", { session_id, question })),
  /** E-15 */ digest: (hours: 1 | 8 | 24) => req<Digest>(`/api/digest?hours=${hours}`),
  /** E-16 */ report: () => req<Report>("/api/report"),
  /** E-17: a plain download link. */ feedbackCsv: "/api/report/feedback.csv",
  /** E-18: fire and forget. */ uiLatency: (event_id: number, ms: number) => { fetch("/api/ui/latency", json("POST", { event_id, ms })).catch(() => {}); },
  /** E-9 */ snapshotUrl: (id: string) => `/snapshot/${id}`,
  /** D89: opt-in phone notifications. */ notify: () => req<NotifyStatus>("/api/notify"),
  /** D89 */ setNotify: (enabled: boolean) => req<NotifyStatus>("/api/notify", json("POST", { enabled })),
  /** D89 */ notifyTest: () => req<{ queued: boolean }>("/api/notify/test", { method: "POST" }),
};
