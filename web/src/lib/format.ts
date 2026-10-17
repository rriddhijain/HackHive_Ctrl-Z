// Formatters with the exact outputs of the old ui.jsx (CONTRACT "Formatting helpers"). The UI only formats numbers.
import type { ChatHow, Event } from "./types";

export const ist = (ts: number | null | undefined): string =>
  ts ? new Date(ts * 1000).toLocaleTimeString("en-GB", { timeZone: "Asia/Kolkata", hour12: false }) : "—";
/** IST calendar date, `17 Oct 2026` (incident report, D92). */
export const istDate = (ts: number | null | undefined): string =>
  ts ? new Date(ts * 1000).toLocaleDateString("en-GB", { timeZone: "Asia/Kolkata", day: "numeric", month: "short", year: "numeric" }) : "—";
export const media = (p: string): string => "/" + p.replace(/^data\//, "media/");
export const v = (x: unknown, unit = ""): string => (x == null ? "—" : `${x}${unit}`);
export const ms = (x: number | null | undefined): string => (x == null ? "—" : `${Math.round(x).toLocaleString("en-US")} ms`);
export const pc = (c: number | null | undefined): string => (c == null ? "—" : `${Math.round(c * 100)}%`);
export const name = (c: string | null | undefined): string => (c ?? "").replaceAll("_", " ");
export const title = (c: string | null | undefined): string => (c ? name(c)[0].toUpperCase() + name(c).slice(1) : "");
/** Pipeline node number: `—` or a rounded en-US integer (B-80). */
export const n = (x: number | null | undefined): string => (x == null ? "—" : Math.round(x).toLocaleString("en-US"));
/** Raw VLM output pretty-printed, or the raw string when it does not parse (B-82). */
export const pretty = (s: string): string => { try { return JSON.stringify(JSON.parse(s), null, 2); } catch { return s; } };

/** Confidence shown everywhere: the live alert's, else the event's peak. */
export const conf = (e: Event): number | null | undefined => e.alert?.confidence ?? e.peak_confidence;
/** Start time of an event (falls back to the alert's store time). */
export const startTs = (e: Event): number | null | undefined => e.start_ts ?? e.alert?.t_stored;

export const STATUS_WORD: Record<string, string> = { open: "Open", closed: "Closed", acknowledged: "Acknowledged", dismissed: "Dismissed" };
export const statusWord = (s: string): string => STATUS_WORD[s] ?? s;

/** Camera status → [dot tone, label] (B-21). */
export type Tone = "ok" | "high" | "critical" | "neutral";
const STATE: Record<string, [Tone, string]> = {
  live: ["ok", "Live"], connecting: ["high", "Connecting"], reconnecting: ["high", "Reconnecting"],
  down: ["critical", "Down"], ended: ["neutral", "Finished"], stopped: ["neutral", "Stopped"],
};
export const camState = (status: string, sourceType: string): [Tone, string] =>
  status === "live" && sourceType === "file" ? ["ok", "Playing"] : STATE[status] ?? ["high", status];

/** How-line prefix of a chat answer (B-75). */
export const how = (h: ChatHow | undefined): string =>
  !h ? "" : (h.digest ? "shift-handover digest · " : h.read_by === "model" ? `question read by the model (${h.read_ms} ms) · ` : "question read by rules · ")
    + (h.mode === "template" ? "template answer"
      : `model answer, ${h.rows} rows, ${h.dropped} sentence${h.dropped === 1 ? "" : "s"} dropped${h.fallback ? " → template" : ""}`);
