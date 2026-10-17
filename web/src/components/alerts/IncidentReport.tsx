"use client";
// Incident report (D92): a print-only document mounted beside the on-screen report. Page 1 is a prefilled incident
// form (the operator ticks the response and signs by hand); page 2 is the evidence log: key frame and mosaic with
// their SHA-256, every model observation, the processing record and provenance. The browser's print dialog makes
// the PDF ("Save as PDF"), so there is no dependency and it works offline.
import { useEffect, useState, type ReactNode } from "react";
import { createPortal, flushSync } from "react-dom";
import type { Top3 } from "@/components/alert-bits";
import { conf, ist, istDate, media, ms, name, pc, startTs, title } from "@/lib/format";
import type { Event, Observation } from "@/lib/types";

type Hashes = Record<string, string | null>;
type Obs = Observation[] | null | false;

/** SHA-256 (hex) of a served file; null where Web Crypto is missing (plain http off localhost) or the fetch fails. */
async function sha256(url: string): Promise<string | null> {
  try {
    const r = await fetch(url);
    if (!r.ok) return null;
    const d = await crypto.subtle.digest("SHA-256", await r.arrayBuffer());
    return Array.from(new Uint8Array(d), (b) => b.toString(16).padStart(2, "0")).join("");
  } catch {
    return null;
  }
}

/**
 * The image hashes, and a print() that waits for them and for the observations so a PDF never carries a
 * half-computed hash or an empty log. A click when everything is ready prints at once, inside the user gesture.
 */
export function useIncidentPrint(e: Event, obs: Obs) {
  const files = e.keyframe_paths ?? [];
  const key = files.join("|");
  const [hashes, setHashes] = useState<{ key: string; h: Hashes } | null>(null);
  const [pending, setPending] = useState(false);
  useEffect(() => {
    let alive = true;
    void Promise.all(files.map(async (f) => [f, await sha256(media(f))] as const))
      .then((kv) => { if (alive) setHashes({ key, h: Object.fromEntries(kv) }); });
    return () => { alive = false; };
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps
  const h = hashes?.key === key ? hashes.h : null;
  const ready = h !== null && obs !== null;
  useEffect(() => {
    if (pending && ready) { setPending(false); window.print(); }
  }, [pending, ready]);
  return { hashes: h, print: () => (ready ? window.print() : setPending(true)) };
}

const num = (x: unknown): number | null => (typeof x === "number" ? x : null);
const str = (x: unknown): string => (typeof x === "string" ? x : "");
/** Wall time with milliseconds in IST, for the processing record. */
const istMs = (ts: number) => `${ist(ts)}.${String(Math.floor((ts % 1) * 1000)).padStart(3, "0")}`;
/** Next most likely categories, `Suspicious activity 3% · Normal 2%`. */
const others = (pairs: [string, number][], skip: string, n = 2) =>
  pairs.filter(([k]) => k !== skip).sort((a, b) => b[1] - a[1]).slice(0, n).map(([k, v]) => `${title(k)} ${pc(v)}`).join(" · ");

/** `HV-20261017-0133`: IST date of the event and its id. */
const reportNo = (e: Event) => {
  const t = startTs(e);
  const d = t ? new Date(t * 1000).toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" }).replaceAll("-", "") : "00000000";
  return `HV-${d}-${String(e.id).padStart(4, "0")}`;
};

const statusLine = (e: Event) =>
  e.status === "open" ? "Open, not yet acknowledged"
    : e.status === "acknowledged" ? "Acknowledged by an operator"
    : e.status === "closed" ? "Closed, no longer observed"
    : e.status === "dismissed" ? (e.dismiss_reason === "relook" ? "Withdrawn after the model's second look" : "Marked a false alarm by an operator")
    : e.status;

const ACTIONS = ["Responded on site", "Police informed", "Medical aid called", "Escalated to supervisor", "False alarm, no action"];
const WRITE: [string, number][] = [["Persons involved (names or descriptions)", 2], ["Injuries or damage", 2], ["Actions taken and notes", 3]];
const SIGN = ["Reported by (operator)", "Signature", "Date and time", "Reviewed by (supervisor)", "Signature", "Date and time"];
const STEPS: [string, string][] = [
  ["t_capture", "Frame captured"], ["t_gate", "Rule fired"], ["t_vlm_start", "Model started"],
  ["t_category", "Verdict known"], ["t_vlm_done", "Summary written"], ["t_db_write", "Stored in the local database"],
];

function Field({ k, ai, children }: { k: string; ai?: boolean; children: ReactNode }) {
  return <div><dt>{k}{ai && <Ai />}</dt><dd>{children}</dd></div>;
}
const Ai = () => <span className="hh-doc-ai">AI</span>;
const Head = ({ no }: { no: string }) => (
  <div className="hh-doc-head"><b>HoneyView</b><span>Security incident report · {no}</span></div>
);

function Figure({ src, label, hash }: { src: string; label: string; hash: string | null | undefined }) {
  return (
    <figure>
      <img src={media(src)} alt={label} />
      <figcaption>
        <b>{label}</b> · {src}
        <code>SHA-256 {hash === undefined ? "computing" : hash ?? "not available in this browser"}</code>
      </figcaption>
    </figure>
  );
}

/** Mounted with the Alerts report; printing the page while it is mounted prints only this (globals.css). */
export function IncidentReport({ event: e, obs, top3, camera, hashes }: {
  event: Event; obs: Obs; top3: Top3 | null | false; camera: string; hashes: Hashes | null;
}) {
  const no = reportNo(e);
  const [at, setAt] = useState(() => Date.now() / 1000);
  // The print time goes on the document, and the title becomes the PDF's default file name.
  useEffect(() => {
    const old = document.title;
    const before = () => { flushSync(() => setAt(Date.now() / 1000)); document.title = `Incident report ${no}`; };
    const after = () => { document.title = old; };
    addEventListener("beforeprint", before);
    addEventListener("afterprint", after);
    return () => { removeEventListener("beforeprint", before); removeEventListener("afterprint", after); };
  }, [no]);
  if (typeof document === "undefined") return null;

  const rows = obs || [];
  const peak = rows.filter((o) => o.category === e.category).sort((a, b) => (num(b.confidence) ?? 0) - (num(a.confidence) ?? 0))[0] ?? rows.at(-1);
  const timing = peak?.timing && typeof peak.timing === "object" ? (peak.timing as Record<string, number>) : null;
  const models = [...new Set(rows.map((o) => str(o.model)).filter(Boolean))];
  const [frame, mosaic] = e.keyframe_paths ?? [];
  const t0 = startTs(e);
  const alt = top3 ? others(top3, e.category) : "";
  const onset = e.alert?.onset_to_alert_ms;

  return createPortal(
    <div className="hh-doc">
      <section>
        <Head no={no} />
        <h1>{title(e.category)}<span className="hh-doc-sev" data-sev={e.severity}>{title(e.severity)}</span></h1>
        <p className="hh-doc-lede">
          Prefilled by HoneyView from event #{e.id} on {istDate(at)} at {ist(at)} IST. Fields marked <Ai /> come from the
          video model: check them against the footage before filing this report.
        </p>

        <h2>1 · Incident details</h2>
        <dl className="hh-doc-fields">
          <Field k="Incident type" ai>{title(e.category)}{e.subtype ? ` (${name(e.subtype)})` : ""}</Field>
          <Field k="Severity">{title(e.severity)}</Field>
          <Field k="Date">{istDate(t0)}</Field>
          <Field k="Detected at">{t0 ? `${ist(t0)} IST` : "—"}</Field>
          <Field k="Location">{camera} ({e.camera_id})</Field>
          <Field k="Last observed">{e.status === "open" ? "Still open when printed" : `${ist(e.end_ts ?? t0)} IST`}</Field>
          <Field k="Confidence" ai>{pc(conf(e))}{e.alert?.rating ? ` (${e.alert.rating})` : ""}</Field>
          <Field k="Next most likely" ai>{alt || "—"}</Field>
          <Field k="People in view (detector)">{num(peak?.people_count) ?? "—"}</Field>
          <Field k="Alert sent">
            {e.time_to_alert_ms == null ? "—" : `${ms(e.time_to_alert_ms)} after the trigger`}{onset != null ? ` · ${ms(onset)} after the onset` : ""}
          </Field>
          <Field k="Status">{statusLine(e)}</Field>
          <Field k="Model looks">{e.n_obs ?? rows.length}</Field>
        </dl>

        <h2>2 · What happened <Ai /></h2>
        <p className="hh-doc-summary">{e.summary ?? "The model had not finished its summary when this was printed."}</p>

        <h2>3 · Response <small>complete by hand</small></h2>
        <div className="hh-doc-checks">{ACTIONS.map((a) => <span key={a}><i />{a}</span>)}</div>
        {WRITE.map(([label, lines]) => (
          <div key={label} className="hh-doc-write">
            <div>{label}</div>
            {Array.from({ length: lines }, (_, i) => <div key={i} className="hh-doc-rule" />)}
          </div>
        ))}

        <h2>4 · Sign-off</h2>
        <div className="hh-doc-sign">
          {SIGN.map((label, i) => <div key={i}><div className="hh-doc-rule" />{label}</div>)}
        </div>
        <p className="hh-doc-foot">{no} · Annex A, the evidence log, follows.</p>
      </section>

      <section>
        <Head no={no} />
        <h1>Annex A · Evidence log</h1>
        <p className="hh-doc-lede">Read from the local database and image files for event #{e.id}. Nothing on this page was typed by a person.</p>
        {frame ? (
          <div className={mosaic ? "hh-doc-frames" : undefined}>
            <Figure src={frame} label="Key frame" hash={hashes?.[frame]} />
            {mosaic && <Figure src={mosaic} label="Mosaic sent to the model" hash={hashes?.[mosaic]} />}
          </div>
        ) : (
          <p>No image is stored for this event{e.seeded ? " (seeded demo history)" : ""}.</p>
        )}

        <h2>Model observations</h2>
        {obs === false ? <p>Could not load the observations.</p> : !rows.length ? <p>No observations.</p> : (
          <table>
            <thead>
              <tr><th>Time (IST)</th><th>Verdict</th><th>Conf.</th><th>Next most likely</th><th>People</th><th>Trigger</th><th>Summary</th></tr>
            </thead>
            <tbody>
              {rows.map((o, i) => (
                <tr key={o.id ?? i}>
                  <td>{ist(o.ts)}</td>
                  <td>{title(str(o.category)) || "—"}</td>
                  <td>{pc(num(o.confidence))}</td>
                  <td>{o.probs ? others(Object.entries(o.probs), str(o.category)) : "—"}</td>
                  <td>{num(o.people_count) ?? "—"}</td>
                  <td>{str(o.trigger) || "—"}</td>
                  <td>{str(o.summary)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {timing && typeof timing.t_capture === "number" && (
          <>
            <h2>Processing record, observation #{peak?.id}</h2>
            <table>
              <tbody>
                {STEPS.filter(([k]) => typeof timing[k] === "number").map(([k, label]) => (
                  <tr key={k}>
                    <td>{label}{k === "t_gate" && str(peak?.trigger) ? ` (${str(peak?.trigger)})` : ""}</td>
                    <td>{istMs(timing[k])} IST</td>
                    <td>{k === "t_capture" ? "" : `+${ms((timing[k] - timing.t_capture) * 1000)}`}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}

        <h2>Provenance</h2>
        <ul>
          <li>
            All analysis ran on this computer: a person detector and the vision-language model{" "}
            {models.length ? models.join(", ") : "(not recorded for this event)"}, open weights, no cloud inference.
          </li>
          <li>
            Source records: event #{e.id}{rows.length ? `, observation${rows.length > 1 ? "s" : ""} #${rows.map((o) => o.id).join(", #")}` : ""},
            camera {e.camera_id}. Times are IST (UTC+5:30); the database stores epoch seconds.
          </li>
          <li>Generated by HoneyView on {istDate(at)} at {ist(at)} IST from the local database.</li>
          {frame && <li>To check an image, run <code>shasum -a 256 {frame}</code> in the HackHive folder: it must print the SHA-256 above.</li>}
        </ul>
      </section>
    </div>,
    document.body,
  );
}
