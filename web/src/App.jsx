import { useEffect, useState } from "react";
import { flushSync } from "react-dom";

// Every number shown here comes from the backend (SSE §9.2, /api/*); the UI only formats it.
const SEV = { critical: "bg-red-600 text-white", high: "bg-orange-500 text-black", medium: "bg-amber-300 text-black" };
const EDGE = { critical: "border-red-600", high: "border-orange-500", medium: "border-amber-300" };
const ist = (ts) => (ts ? new Date(ts * 1000).toLocaleTimeString("en-GB", { timeZone: "Asia/Kolkata", hour12: false }) : "—");
const media = (p) => "/" + p.replace(/^data\//, "media/");
const v = (x, unit = "") => (x == null ? "—" : `${x}${unit}`);
const pc = (c) => (c == null ? "—" : `${Math.round(c * 100)}%`);
const name = (c) => c?.replaceAll("_", " ");
const post = (u, body) => fetch(u, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
const STATUS = { connecting: "connecting", live: "live", reconnecting: "reconnecting", down: "down", ended: "finished", stopped: "stopped" };
const STATUS_COLOR = { live: "text-emerald-400", ended: "text-sky-400", down: "text-red-400" };
// MJPEG tiles hold one HTTP/1.1 connection each (browser cap: 6 per host): load them via the other loopback name
const STREAM = `${location.protocol}//${location.hostname === "localhost" ? "127.0.0.1" : location.hostname === "127.0.0.1" ? "localhost" : location.hostname}:${location.port}`;

let audio = null;
function beep() {
  if (!audio) return;
  const o = audio.createOscillator(), g = audio.createGain();
  o.frequency.value = 880; g.gain.value = 0.25;
  o.connect(g).connect(audio.destination);
  o.start(); o.stop(audio.currentTime + 0.5);
}

export default function App() {
  const [cams, setCams] = useState([]);
  const [events, setEvents] = useState({});
  const [m, setM] = useState(null);
  const [traces, setTraces] = useState({});
  const [toasts, setToasts] = useState([]);
  const [view, setView] = useState("dashboard");
  const [conn, setConn] = useState(false);
  const [sound, setSound] = useState(false);

  const loadCams = () => fetch("/api/cameras").then((r) => r.json()).then(setCams);
  const merge = (id, patch) => setEvents((s) => ({ ...s, [id]: { ...s[id], ...patch } }));

  useEffect(() => {
    loadCams();
    fetch("/api/events?limit=50").then((r) => r.json())
      .then((rows) => setEvents((s) => Object.fromEntries([...rows.map((e) => [e.id, e]), ...Object.entries(s)])));
    const es = new EventSource("/sse");
    const on = (t, f) => es.addEventListener(t, (e) => f(JSON.parse(e.data)));
    es.onopen = () => setConn(true);
    es.onerror = () => setConn(false);
    let camKeys = "";
    on("metrics", (x) => {
      const k = Object.entries(x.cameras).map(([id, c]) => id + c.status).join();   // ids or a status changed
      if (k !== camKeys) { camKeys = k; loadCams(); }
      setM(x);
    });
    on("alert", (a) => {
      flushSync(() => {   // commit the card now, then measure after the paint
        merge(a.event_id, { id: a.event_id, alert: a, camera_id: a.camera_id, category: a.category, severity: a.severity,
          peak_confidence: a.confidence, time_to_alert_ms: a.trigger_to_alert_ms, status: "open" });
        if (a.severity === "critical") setToasts((t) => [...t, a]);
      });
      requestAnimationFrame(() => setTimeout(() => fetch("/api/ui/latency", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ event_id: a.event_id, ms: performance.timeOrigin + performance.now() - a.t_stored * 1000 }),
      }), 0));
      if (a.severity === "critical") {
        beep();
        setTimeout(() => setToasts((t) => t.filter((x) => x !== a)), 10000);
      }
    });
    for (const t of ["event_open", "event_update", "event_close"]) on(t, (e) => merge(e.id, e));
    on("trace", (tr) => setTraces((s) => ({ ...s, [tr.camera_id]: tr })));
    on("camera_status", loadCams);
    return () => es.close();
  }, []);

  const armSound = () => {
    audio ??= new AudioContext();
    audio.resume();
    setSound(true);
    beep();
  };
  const feed = Object.values(events).filter((e) => e.status !== "dismissed").sort((a, b) => b.id - a.id).slice(0, 50);
  const camName = (id) => cams.find((c) => c.id === id)?.name ?? id;
  const mode = m?.mode;
  const switchMode = async (k) => {   // stops every source of the other mode; history stays
    if (k === mode) return;
    await post("/api/mode", { mode: k });
    setM((x) => ({ ...x, mode: k }));
    loadCams();
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <header className="sticky top-0 z-40 border-b border-zinc-800 bg-zinc-950 px-4 py-2">
        <div className="mb-1 flex items-center gap-4">
          <h1 className="text-lg font-bold">HackHive</h1>
          <div className="flex overflow-hidden rounded border border-zinc-600 text-sm">
            {["clips", "live"].map((k) => (
              <button key={k} onClick={() => switchMode(k)}
                className={`px-3 py-0.5 capitalize ${mode === k ? "bg-sky-500 font-semibold text-black" : "bg-zinc-900 text-zinc-300"}`}>{k}</button>
            ))}
          </div>
          {["dashboard", "workflow"].map((k) => (
            <button key={k} onClick={() => setView(k)}
              className={`rounded px-3 py-0.5 text-sm capitalize ${view === k ? "bg-zinc-100 text-zinc-900" : "bg-zinc-800"}`}>{k}</button>
          ))}
          <span className={`text-xs ${conn ? "text-emerald-400" : "text-red-400"}`}>● {conn ? "connected" : "reconnecting"}</span>
          <span className="text-xs text-zinc-500">{m?.vlm?.model}</span>
          <button onClick={armSound} className={`ml-auto rounded px-2 py-0.5 text-xs ${sound ? "bg-zinc-800" : "bg-red-700"}`}>
            {sound ? "sound on" : "click to arm alert sound"}
          </button>
        </div>
        <Strip m={m} notice={mode === "live" && cams.length > 2 && "3+ live cameras: alerts may slow"} />
      </header>

      {view === "dashboard" ? (
        <main className="grid gap-4 p-4 lg:grid-cols-[1fr_440px]">
          <section className="grid content-start gap-3 sm:grid-cols-2">
            {cams.map((c) => <Tile key={c.id} c={c} cm={m?.cameras?.[c.id]} onRemove={loadCams}
              evs={Object.values(events).filter((e) => e.camera_id === c.id).sort((a, b) => a.id - b.id)} />)}
            {mode === "clips" && <><Playlist playing={cams[0]?.source} onPlay={loadCams} /><Upload onDone={loadCams} /></>}
            {mode === "live" && <AddSource cams={cams} onDone={loadCams} />}
          </section>
          <aside>
            <h2 className="mb-2 text-sm font-semibold text-zinc-400">INCIDENTS</h2>
            <div className="space-y-2">
              {feed.length ? feed.map((e) => <Card key={e.id} e={e} camName={e.camera_name ?? camName(e.camera_id)} />)
                : <p className="text-sm text-zinc-500">No incidents.</p>}
            </div>
          </aside>
        </main>
      ) : (
        <Workflow cams={cams} traces={traces} m={m} />
      )}

      <div className="fixed bottom-4 right-4 z-50 space-y-2">
        {toasts.map((a) => (
          <div key={a.event_id} onClick={() => setToasts((t) => t.filter((x) => x !== a))}
            className="w-96 cursor-pointer rounded border-2 border-red-300 bg-red-700 p-3 shadow-xl">
            <div className="font-bold uppercase">Critical · {name(a.category)}</div>
            <div className="text-sm">{camName(a.camera_id)} · {pc(a.confidence)} {a.rating} · trigger → alert {a.trigger_to_alert_ms} ms</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Strip({ m, notice }) {
  const x = m?.vlm ?? {}, o2a = m?.latency?.onset_to_alert_ms ?? {}, s2c = m?.latency?.store_to_card_ms ?? {};
  const items = [
    ["GPU duty (60 s)", v(x.gpu_duty_pct, " %"), "Share of the last 60 s the model was busy. Target ≤ 60 % average with 3 cameras."],
    ["onset → alert", o2a.n ? `${o2a.last} ms (p50 ${o2a.p50}, n=${o2a.n})` : "—",
      "Labelled incident onset in the clip → alert (§12). Only for labelled clips played once (uploads, bench/labels.csv); live onset is measured from 240 fps phone video."],
    ["model time-to-alert p95", v(x.alert_p95_ms, " ms"), "Newest frame captured → category known, p95 over all calls. Never quoted alone (D50)."],
    ["VLM call p50/p95", `${v(x.p50_ms)} / ${v(x.p95_ms)} ms`],
    ["store → card", s2c.n ? `${s2c.p95} ms p95 (last ${s2c.last}, n=${s2c.n})` : "—",
      "Event row stored → card painted in this browser; budget ≤ 100 ms. Valid only when the browser runs on the server machine (it compares the two clocks); readings from other devices are ignored."],
    ["baselines skipped", v(x.baselines_skipped), "Baseline calls skipped because the scene had not changed (D42)."],
    ["vetoes", v(x.vetoes), "Detector cross-check vetoes (E-7)."],
    ["queue", v(x.queue_depth)],
    ["calls", v(x.calls_total)],
    ["preempted", v(x.preemptions)],
    ["VLM errors", v(x.errors)],
    ["memory", v(m?.system?.mem_used_pct, " %")],
  ];
  return (
    <div className="flex flex-wrap gap-x-5 gap-y-0.5 text-xs">
      {items.map(([k, val, tip]) => (
        <div key={k} title={tip}>
          <span className="text-zinc-500">{k} </span>
          <b className={`tabular-nums ${k === "store → card" && s2c.p95 > 100 ? "text-red-400" : ""}`}>{val}</b>
        </div>
      ))}
      {notice && <b className="text-amber-400" title="P2b: 3 busy sources pushed GPU duty above 90 %">⚠ {notice}</b>}
    </div>
  );
}

function Tile({ c, cm, onRemove, evs }) {
  const status = cm?.status ?? c.status;
  const remove = async () => {   // one click: stops the source and releases the device
    await fetch(`/api/cameras/${c.id}`, { method: "DELETE" });
    onRemove();
  };
  return (
    <div className="overflow-hidden rounded bg-zinc-900">
      <div className="flex items-center gap-2 px-2 py-1 text-sm">
        <b>{c.id}</b>
        <span className="truncate">{c.name}</span>
        <span className={`text-xs ${STATUS_COLOR[status] ?? "text-amber-400"}`}>{STATUS[status] ?? status}</span>
        <span className="ml-auto whitespace-nowrap text-xs text-zinc-400">
          {v(cm?.people)} ppl · YOLO {v(cm?.yolo_ms_p50, " ms")} · keep-up {pc(cm?.keep_up)}
        </span>
        <button onClick={remove} title="Stop and release this source" className="text-zinc-400 hover:text-red-400">■</button>
      </div>
      <img src={`${STREAM}/stream/${c.id}`} alt={c.name} className="aspect-video w-full bg-black object-contain" />
      <div className="px-2 py-1 text-xs">
        <span className="text-zinc-500">now: </span>{cm?.now?.text ?? "—"}
        <span className="text-zinc-500"> · as of {ist(cm?.now?.ts)} ({cm?.now?.source ?? "—"})</span>
      </div>
      {status === "ended" && <Result c={c} evs={evs.filter((e) => e.status !== "dismissed")} />}
    </div>
  );
}

function Result({ c, evs }) {   // a clip played once has finished: what it found, against the label if there is one
  const at = (ts) => (ts && c.t_first ? `${(ts - c.t_first).toFixed(1)} s` : "—");
  const hit = evs.find((e) => e.category === c.label);
  return (
    <div className="space-y-1 border-t border-zinc-800 px-2 py-2 text-sm">
      <div className="text-xs font-semibold text-zinc-400">RESULT{c.label && ` · label: ${name(c.label)}`}</div>
      {c.onset_s != null && (
        <div>incident at <b>{c.onset_s} s</b> → {hit ? <>alert at <b>{at(hit.alert?.t_stored ?? hit.start_ts)}</b></> : "no matching alert"}</div>
      )}
      {evs.length ? evs.map((e) => (
        <div key={e.id}>
          <span className={`rounded px-1.5 text-xs font-bold uppercase ${SEV[e.severity] ?? "bg-zinc-700"}`}>{name(e.category)}</span>
          {" "}<b>{pc(e.peak_confidence)}</b> · alert at {at(e.alert?.t_stored ?? e.start_ts)} in the clip
          <div className="text-zinc-300">{e.summary ?? <i className="text-zinc-500">summary pending…</i>}</div>
        </div>
      )) : <div className="font-semibold text-emerald-400">No incidents.</div>}
    </div>
  );
}

function Playlist({ playing, onPlay }) {   // Act 1: one click plays a clip once; it replaces the one playing
  const [clips, setClips] = useState([]);
  const [msg, setMsg] = useState("");
  useEffect(() => { fetch("/api/clips").then((r) => r.json()).then(setClips); }, []);
  const play = async (x) => {
    const r = await post("/api/clips/play", { path: x.path });
    setMsg(r.ok ? "" : `rejected: ${(await r.json()).detail}`);
    onPlay();
  };
  return (
    <div className="rounded bg-zinc-900 p-2">
      <div className="mb-1 text-xs font-semibold text-zinc-400">DEMO CLIPS · one at a time, played once</div>
      <div className="space-y-0.5">
        {clips.map((x) => (
          <button key={x.path} onClick={() => play(x)}
            className={`flex w-full items-center gap-2 rounded px-2 py-0.5 text-left text-sm hover:bg-zinc-700 ${playing === x.path ? "bg-zinc-700" : ""}`}>
            <span>▶</span><span className="truncate">{x.name}</span>
            <span className="ml-auto whitespace-nowrap text-xs text-zinc-400">
              {x.folder} · {x.label ? name(x.label) : "unlabelled"}{x.onset_s != null && ` @ ${x.onset_s} s`}
            </span>
          </button>
        ))}
      </div>
      {msg && <div className="mt-1 text-xs text-red-400">{msg}</div>}
    </div>
  );
}

function AddSource({ cams, onDone }) {   // Act 2: devices (iPhone via Continuity, webcams) and phone stream URLs
  const [devs, setDevs] = useState(null);
  const [url, setUrl] = useState("");
  const [msg, setMsg] = useState("");
  useEffect(() => { fetch("/api/devices").then((r) => r.json()).then(setDevs); }, []);
  const running = new Set(cams.map((c) => c.source));
  const add = async (source, label) => {
    const r = await post("/api/cameras", { source, name: label });
    setMsg(r.ok ? "" : `rejected: ${(await r.json()).detail}`);
    onDone();
  };
  return (
    <div className="space-y-2 rounded bg-zinc-900 p-2 text-sm">
      <div className="text-xs font-semibold text-zinc-400">ADD A LIVE SOURCE</div>
      {devs == null ? <div className="text-xs text-zinc-500">looking for cameras…</div> : (
        <div className="flex flex-wrap gap-1">
          {devs.map((d) => (
            <button key={d.source} disabled={running.has(d.source)} onClick={() => add(d.source, d.name)}
              className="rounded bg-zinc-700 px-2 py-0.5 hover:bg-zinc-600 disabled:opacity-40">+ {d.name}</button>
          ))}
        </div>
      )}
      <form className="flex gap-1" onSubmit={(e) => { e.preventDefault(); if (url.trim()) add(url.trim(), null); }}>
        <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="http://192.168.43.20:8080/video or rtsp://…"
          className="min-w-0 flex-1 rounded bg-zinc-800 px-2 py-0.5" />
        <button className="rounded bg-zinc-700 px-2 py-0.5 hover:bg-zinc-600">Add URL</button>
      </form>
      {msg && <div className="text-xs text-red-400">{msg}</div>}
    </div>
  );
}

function Upload({ onDone }) {
  const [msg, setMsg] = useState("");
  const send = async (f) => {
    if (!f) return;
    setMsg(`uploading ${f.name}…`);
    const r = await fetch(`/api/cameras/upload?name=${encodeURIComponent(f.name)}`, { method: "POST", body: f });
    const j = await r.json();
    setMsg(r.ok ? `${j.id} added: ${j.name}` : `rejected: ${j.detail}`);
    onDone();
  };
  return (
    <label onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); send(e.dataTransfer.files[0]); }}
      className="grid aspect-video cursor-pointer place-items-center rounded border-2 border-dashed border-zinc-700 text-center hover:border-zinc-400">
      <input type="file" accept=".mp4,.mov,.avi,.mkv" hidden onChange={(e) => send(e.target.files[0])} />
      <div className="text-sm text-zinc-400">
        Drop a video or click to upload
        <div className="text-xs text-zinc-500">mp4 · mov · avi · mkv, ≤ 500 MB, plays once (replaces the clip playing)</div>
        <div className="mt-1 text-xs text-zinc-200">{msg}</div>
      </div>
    </label>
  );
}

function Card({ e, camName }) {
  const [top3, setTop3] = useState(null);
  useEffect(() => {   // history card (no live alert): top-3 from the event's peak observation
    if (e.alert) return;
    fetch(`/api/events/${e.id}`).then((r) => r.json()).then((d) => {
      const o = d.observations?.filter((o) => o.probs).sort((a, b) => b.probs[e.category] - a.probs[e.category])[0];
      if (o) setTop3(Object.entries(o.probs).sort((a, b) => b[1] - a[1]).slice(0, 3));
    });
  }, [e.id, e.n_obs]);   // the first observation is stored after the alert
  const t3 = e.alert?.top3 ?? top3;
  const thumb = e.keyframe_paths?.[0];
  const ack = () => fetch(`/api/events/${e.id}/ack`, { method: "POST" });
  return (
    <div className={`flex gap-2 rounded border-l-4 bg-zinc-900 p-2 ${EDGE[e.severity] ?? "border-zinc-600"}`}>
      {thumb ? <img src={media(thumb)} className="h-20 w-32 shrink-0 rounded object-cover" alt="" />
        : <div className="grid h-20 w-32 shrink-0 place-items-center rounded bg-zinc-800 text-xs text-zinc-500">key frame…</div>}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 text-sm">
          <span className={`rounded px-1.5 text-xs font-bold uppercase ${SEV[e.severity] ?? "bg-zinc-700"}`}>{name(e.category)}</span>
          <span className="truncate text-zinc-300">{camName}</span>
          <span className="ml-auto text-xs text-zinc-500">{ist(e.start_ts ?? e.alert?.t_stored)} IST</span>
        </div>
        <div className="mt-1 flex flex-wrap gap-x-3 text-xs">
          <span><b>{pc(e.alert?.confidence ?? e.peak_confidence)}</b> {e.alert?.rating}
            {e.alert && e.peak_confidence > e.alert.confidence && <span className="text-zinc-500"> (peak {pc(e.peak_confidence)})</span>}</span>
          <span>trigger → alert <b>{v(e.time_to_alert_ms, " ms")}</b></span>
          {e.alert?.onset_to_alert_ms != null && <span>onset → alert <b>{e.alert.onset_to_alert_ms} ms</b></span>}
          <span className="ml-auto text-zinc-400">{e.status}</span>
        </div>
        {t3 && (
          <div className="mt-1">
            <div className="flex h-2 overflow-hidden rounded bg-zinc-800">
              {t3.map(([k, c], i) => (
                <div key={k} style={{ width: `${c * 100}%` }} className={i === 0 ? "bg-sky-400" : i === 1 ? "bg-zinc-400" : "bg-zinc-600"} />
              ))}
            </div>
            <div className="mt-0.5 flex gap-3 text-[11px] text-zinc-400">
              {t3.map(([k, c]) => <span key={k}>{name(k)} {pc(c)}</span>)}
            </div>
          </div>
        )}
        <p className="mt-1 text-sm text-zinc-200">{e.summary ?? <i className="text-zinc-500">summary pending…</i>}</p>
      </div>
      {e.status === "open" && (
        <button onClick={ack} className="self-start rounded bg-zinc-700 px-2 py-0.5 text-xs hover:bg-zinc-600">Ack</button>
      )}
    </div>
  );
}

function Box({ label, val }) {
  return (
    <div className="rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-center">
      <div className="text-[11px] text-zinc-400">{label}</div>
      <div className="text-sm font-bold tabular-nums">{val}</div>
    </div>
  );
}

function Workflow({ cams, traces, m }) {
  const s2c = m?.latency?.store_to_card_ms;
  return (
    <main className="space-y-4 p-4">
      {cams.map((c) => {
        const t = traces[c.id], cm = m?.cameras?.[c.id];
        const boxes = [["capture", v(cm?.capture_fps, " fps")], ["YOLO + ByteTrack", v(cm?.yolo_ms_p50, " ms")],
          ...(t?.stages ?? []).map((s) => [s.name, `${s.ms} ms`]), ["SSE → card (p95)", v(s2c?.p95, " ms")]];
        return (
          <div key={c.id} className="rounded bg-zinc-900 p-3">
            <div className="mb-2 text-sm">
              <b>{c.id}</b> {c.name}
              {t ? <span className="text-zinc-400"> · last call {t.trigger} at {ist(t.ts)} IST · model time-to-alert <b className="text-zinc-100">{v(t.model_tta_ms, " ms")}</b></span>
                : <span className="text-zinc-500"> · waiting for the first model call</span>}
            </div>
            <div className="mb-3 flex flex-wrap items-center gap-1">
              {boxes.map(([k, val], i) => (
                <div key={k} className="flex items-center gap-1">
                  {i > 0 && <span className="text-zinc-600">→</span>}
                  <Box label={k} val={val} />
                </div>
              ))}
            </div>
            {t && (
              <div className="grid gap-3 lg:grid-cols-[576px_1fr]">
                <img src={t.mosaic_url} alt="mosaic sent to the VLM" className="w-full max-w-[576px] rounded" />
                <div className="min-w-0 space-y-2 text-xs">
                  <div><div className="text-zinc-500">hints sent with the mosaic</div><div>{t.hints}</div></div>
                  <div><div className="text-zinc-500">raw VLM JSON (streamed)</div>
                    <pre className="whitespace-pre-wrap break-all rounded bg-black p-2 font-mono">{t.raw_json}</pre></div>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </main>
  );
}
