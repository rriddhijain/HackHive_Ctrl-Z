import { Fragment, useEffect, useRef, useState } from "react";
import { flushSync } from "react-dom";
import * as Ic from "./icons.jsx";
import { Button, Chip, Dot, Empty, Label, Segmented, Skeleton, Top3, SEV_BG, SEV_TEXT, STATE, getJSON, ist, media, ms, name, pc, post, title, v } from "./ui.jsx";

// Every number shown here comes from the backend (SSE §9.2, /api/*); the UI only formats it.
// P5b layout (D76): top bar · camera grid · right rail (Alerts | Ask | Pipeline) with a critical banner above it.

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
  const [evLoad, setEvLoad] = useState("loading");   // loading | ok | error
  const [m, setM] = useState(null);
  const [traces, setTraces] = useState({});
  const [tab, setTab] = useState("alerts");
  const [conn, setConn] = useState(false);
  const [sound, setSound] = useState(false);
  const [openEv, setOpenEv] = useState(null);   // the event a card, banner or chat citation opened
  const askRef = useRef(null);

  const loadCams = () => getJSON("/api/cameras").then(setCams).catch(() => {});   // keep the last list
  const merge = (id, patch) => setEvents((s) => ({ ...s, [id]: { ...s[id], ...patch } }));

  useEffect(() => {
    loadCams();
    getJSON("/api/events?limit=50")
      .then((rows) => { setEvents((s) => Object.fromEntries([...rows.map((e) => [e.id, e]), ...Object.entries(s)])); setEvLoad("ok"); })
      .catch(() => setEvLoad("error"));
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
      });
      requestAnimationFrame(() => setTimeout(() => fetch("/api/ui/latency", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ event_id: a.event_id, ms: performance.timeOrigin + performance.now() - a.t_stored * 1000 }),
      }), 0));
      if (a.severity === "critical") beep();
    });
    for (const t of ["event_open", "event_update", "event_close"]) on(t, (e) => merge(e.id, e));
    on("trace", (tr) => setTraces((s) => ({ ...s, [tr.camera_id]: tr })));
    on("camera_status", loadCams);
    return () => es.close();
  }, []);

  useEffect(() => {   // Esc closes the event dialog; "/" jumps to Ask
    const key = (e) => {
      if (e.key === "Escape") setOpenEv(null);
      else if (e.key === "/" && !/^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName)) {
        e.preventDefault();
        setTab("ask");
        setTimeout(() => askRef.current?.focus(), 0);
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, []);

  const armSound = () => {
    audio ??= new AudioContext();
    audio.resume();
    setSound(true);
    beep();
  };
  const ack = async (id) => {
    const r = await fetch(`/api/events/${id}/ack`, { method: "POST" });
    if (r.ok) { const { observations, ...e } = await r.json(); merge(e.id, e); }
  };
  const all = Object.values(events);
  const feed = all.filter((e) => e.status !== "dismissed").sort((a, b) => b.id - a.id).slice(0, 50);
  // The banner holds every critical alert until someone acknowledges it, even after the event closes.
  const critical = feed.filter((e) => e.severity === "critical" && (e.alert || e.status === "open") && e.status !== "acknowledged");
  const camName = (e) => e.camera_name ?? cams.find((c) => c.id === e.camera_id)?.name ?? name(e.camera_id);
  const mode = m?.mode;
  const switchMode = async (k) => {   // stops every source of the other mode; history stays
    if (k === mode) return;
    await post("/api/mode", { mode: k });
    setM((x) => ({ ...x, mode: k }));
    loadCams();
  };
  const camEvents = (id) => all.filter((e) => e.camera_id === id).sort((a, b) => a.id - b.id);
  const tile = (c) => <Tile key={c.id} c={c} cm={m?.cameras?.[c.id]} onRemove={loadCams} evs={camEvents(c.id)} />;
  const nOpen = feed.filter((e) => e.status === "open").length;

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <TopBar m={m} mode={mode} switchMode={switchMode} conn={conn} sound={sound} armSound={armSound} />
      <div className="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)_400px]">
        <main className="min-h-0 overflow-y-auto">
          <div className="flex h-10 items-center gap-2 border-b border-line px-4">
            <Label>{mode === "live" ? "Live sources" : "Now playing"}</Label>
            <span className="font-mono text-11 text-fg-3">{cams.length}</span>
            {mode === "live" && cams.length > 2 && (
              <span className="ml-auto flex items-center gap-1.5 text-12 text-high" title="P2b: 3 busy sources pushed GPU duty above 90 %">
                <Ic.Alert size={14} />3+ live cameras: alerts may slow
              </span>
            )}
          </div>
          <div className="space-y-4 p-4">
            {mode == null && <div className="grid gap-4 xl:grid-cols-2"><Skeleton className="aspect-video" /><Skeleton className="aspect-video" /></div>}
            {mode === "clips" && (
              <>
                <div className="grid gap-4 xl:grid-cols-2">
                  {cams.length ? cams.map((c) => (
                    <Fragment key={c.id}>{tile(c)}<Verdict c={c} status={m?.cameras?.[c.id]?.status ?? c.status}
                      evs={camEvents(c.id).filter((e) => e.status !== "dismissed")} /></Fragment>
                  )) : (
                    <>
                      <div className="grid aspect-video place-items-center rounded-md border border-line bg-surface">
                        <Empty icon={Ic.Play} title="No clip playing" hint="Play a clip from the library below, or upload a video." />
                      </div>
                      <Verdict />
                    </>
                  )}
                </div>
                <Library playing={cams[0]?.source} onPlay={loadCams} />
              </>
            )}
            {mode === "live" && (
              <div className="grid gap-4 xl:grid-cols-2">
                {cams.map(tile)}
                <AddSource cams={cams} onDone={loadCams} />
              </div>
            )}
          </div>
        </main>

        <aside className="flex min-h-0 flex-col border-l border-line">
          {critical.length > 0 && <Banner key={critical[0].id} list={critical} camName={camName} onAck={ack} onOpen={setOpenEv} />}
          <div role="tablist" aria-label="Rail" className="flex h-10 shrink-0 items-stretch gap-4 border-b border-line px-4">
            {[["alerts", "Alerts", nOpen], ["ask", "Ask"], ["pipeline", "Pipeline"]].map(([k, t, n]) => (
              <button key={k} role="tab" id={`tab-${k}`} aria-selected={tab === k} aria-controls={`panel-${k}`} onClick={() => setTab(k)}
                className={`-mb-px flex items-center gap-1.5 border-b-2 text-13 font-medium ${tab === k ? "border-accent-fg text-fg" : "border-transparent text-fg-3 hover:text-fg"}`}>
                {t}{n ? <span className="font-mono text-11 text-fg-3">{n}</span> : null}
              </button>
            ))}
            <span className="ml-auto self-center text-11 text-fg-3">
              <kbd className="rounded border border-line-strong px-1 font-mono">/</kbd> to ask
            </span>
          </div>
          <div role="tabpanel" id="panel-alerts" aria-labelledby="tab-alerts" className={tab === "alerts" ? "min-h-0 flex-1 overflow-y-auto" : "hidden"}>
            <Alerts feed={feed} load={evLoad} camName={camName} onOpen={setOpenEv} onAck={ack} />
          </div>
          <div role="tabpanel" id="panel-ask" aria-labelledby="tab-ask" className={tab === "ask" ? "min-h-0 flex-1" : "hidden"}>
            <Chat onOpen={setOpenEv} inputRef={askRef} />
          </div>
          <div role="tabpanel" id="panel-pipeline" aria-labelledby="tab-pipeline" className={tab === "pipeline" ? "min-h-0 flex-1 overflow-y-auto" : "hidden"}>
            <Pipeline cams={cams} traces={traces} m={m} />
          </div>
        </aside>
      </div>

      {openEv && <EventDialog e={{ ...openEv, ...events[openEv.id] }} camName={camName} onAck={ack} onClose={() => setOpenEv(null)} />}
    </div>
  );
}

function TopBar({ m, mode, switchMode, conn, sound, armSound }) {
  const x = m?.vlm ?? {}, o2a = m?.latency?.onset_to_alert_ms ?? {};
  return (
    <header className="relative flex h-12 shrink-0 items-center border-b border-line px-4">
      <div className="flex items-center gap-2">
        <Ic.Hive size={20} />
        <span className="text-15 font-semibold tracking-tight">HackHive</span>
        <span className="hidden text-13 text-fg-3 2xl:inline">Incident console</span>
      </div>
      <div className="absolute left-1/2 -translate-x-1/2">
        <Segmented label="Source mode" value={mode} options={[["clips", "Clips"], ["live", "Live"]]} onChange={switchMode} />
      </div>
      <div className="ml-auto flex min-w-0 max-w-[calc(50%-68px)] items-center justify-end gap-2.5 font-mono text-12 text-fg-3">
        <span className="truncate" title="Vision-language model, running in Ollama on this machine">{x.model ?? "—"}</span>
        <span className="whitespace-nowrap" title="Share of the last 60 s the model was busy. Target ≤ 60 % average with 3 cameras.">
          GPU <span className="text-fg-2">{x.gpu_duty_pct == null ? "—" : `${Math.round(x.gpu_duty_pct)}%`}</span>
        </span>
        <span className="whitespace-nowrap" title="Labelled incident onset in the clip → alert (§12), p50. Only for labelled clips played once.">
          onset→alert p50 <span className="text-fg-2">{o2a.n ? ms(o2a.p50) : "—"}</span>
        </span>
        <span className="inline-flex h-6 items-center gap-1.5 whitespace-nowrap rounded border border-line-strong px-2 font-sans text-11 font-medium text-fg-2"
          title={conn ? "Connected to the local server; no network needed" : "Lost the local server; retrying"}>
          <Dot className={conn ? "bg-ok" : "bg-crit"} />{conn ? "Local · offline" : "Reconnecting"}
        </span>
        <Clock />
        {sound ? (   // armed: a quiet bell; clicking it again plays the test beep
          <Button size="sm" variant="ghost" onClick={armSound} aria-label="Alert sound on, click to test" title="Alert sound on, click to test" className="w-6 px-0">
            <Ic.Bell size={14} />
          </Button>
        ) : <Button size="sm" variant="primary" onClick={armSound} className="font-sans"><Ic.BellOff size={14} />Arm sound</Button>}
      </div>
    </header>
  );
}

function Clock() {
  const [t, setT] = useState(Date.now() / 1000);
  useEffect(() => { const i = setInterval(() => setT(Date.now() / 1000), 1000); return () => clearInterval(i); }, []);
  return <span className="whitespace-nowrap text-fg-2">{ist(t)} IST</span>;
}

function Banner({ list, camName, onAck, onOpen }) {
  const e = list[0];
  return (
    <div role="alert" className="shrink-0 animate-enter border-b border-crit/40 bg-crit-bg px-4 py-3">
      <div className="flex items-center gap-3">
        <Ic.Alert size={18} className="text-crit" />
        <button onClick={() => onOpen(e)} className="min-w-0 flex-1 text-left">
          <div className="text-13 font-semibold text-fg">Critical · {title(e.category)}</div>
          <div className="truncate font-mono text-12 text-fg-2">
            {ist(e.start_ts ?? e.alert?.t_stored)} IST · {pc(e.alert?.confidence ?? e.peak_confidence)} · {camName(e)}
          </div>
        </button>
        <Button variant="primary" size="sm" onClick={() => onAck(e.id)}>Ack</Button>
      </div>
      {list.length > 1 && <div className="mt-1 pl-[30px] text-12 text-fg-2">{list.length - 1} more unacknowledged</div>}
    </div>
  );
}

function Tile({ c, cm, onRemove, evs }) {
  const status = cm?.status ?? c.status;
  const [dot, label] = status === "live" && c.source_type === "file" ? ["bg-ok", "Playing"] : STATE[status] ?? ["bg-high", status];
  const hot = [...evs].reverse().find((e) => e.status === "open" && (e.severity === "critical" || e.severity === "high"));
  const remove = async () => {   // one click: stops the source and releases the device
    await fetch(`/api/cameras/${c.id}`, { method: "DELETE" });
    onRemove();
  };
  return (
    <article className="relative flex flex-col overflow-hidden rounded-md border border-line bg-surface">
      <div className="relative">
        {status === "connecting" ? <div className="aspect-video bg-black" /> : <Live id={c.id} alt={c.name} />}
        {status === "connecting" && (
          <div className="absolute inset-0 grid place-items-center bg-page">
            <Skeleton className="absolute inset-0 rounded-none" /><span className="relative text-12 text-fg-3">Connecting…</span>
          </div>
        )}
        {status === "down" && (
          <div className="absolute inset-0 grid place-items-center bg-black/60">
            <Empty title="Source down" hint="Stop it, then add it again." />
          </div>
        )}
        {hot && (
          <Chip className={`absolute left-2 top-2 ${hot.severity === "critical" ? "bg-crit text-white" : "bg-high text-black"}`}>
            {title(hot.category)} · <span className="font-mono">{pc(hot.alert?.confidence ?? hot.peak_confidence)}</span>
          </Chip>
        )}
        <div className="absolute right-2 top-2 flex items-center gap-1">
          <Chip className="bg-black/60 font-mono tracking-wider text-white">{c.source_type === "file" ? "CLIP" : "LIVE"}</Chip>
          <button onClick={remove} title="Stop and release this source" aria-label={`Stop ${c.name}`}
            className="grid size-5 place-items-center rounded bg-black/60 text-white hover:bg-black"><Ic.Stop size={12} /></button>
        </div>
        <div className="absolute bottom-2 left-2 flex h-6 max-w-[calc(100%-16px)] items-center gap-1.5 rounded bg-black/60 px-2 text-12 text-white">
          <Dot className={dot} /><span className="truncate font-medium">{c.name}</span><span className="whitespace-nowrap text-white/70">{label}</span>
        </div>
      </div>
      <div className="flex flex-1 flex-col justify-center gap-0.5 border-t border-line px-3 py-2">
        <p className="truncate text-13 text-fg" title={cm?.now?.text}><span className="text-fg-3">Now </span>{cm?.now?.text ?? "—"}</p>
        <p className="truncate font-mono text-11 text-fg-3">
          {c.id} · {v(cm?.people)} ppl · YOLO {ms(cm?.yolo_ms_p50)} · keep-up {pc(cm?.keep_up)} · as of {ist(cm?.now?.ts)} {cm?.now?.source ?? ""}
        </p>
      </div>
      {hot && <div className={`pointer-events-none absolute inset-0 rounded-md ring-2 ring-inset ${hot.severity === "critical" ? "ring-crit" : "ring-high"}`} />}
    </article>
  );
}

// Live view at ~10 fps, double-buffered (D72): each snapshot is fetched whole, checked for the JPEG start/end
// markers, decoded off-screen, and only then swapped in. A failed or truncated frame is skipped, so the tile keeps
// the last good one and never paints a half-loaded (grey) frame, which Safari did with the MJPEG stream.
function Live({ id, alt }) {
  const ref = useRef(null);
  useEffect(() => {
    let alive = true, shown = null;
    const tick = async () => {
      const t0 = performance.now();
      let url = null;
      try {
        const r = await fetch(`/snapshot/${id}`, { cache: "no-store" });
        const b = new Uint8Array(await r.arrayBuffer()), n = b.length;
        if (r.ok && n > 4 && b[0] === 0xff && b[1] === 0xd8 && b[n - 2] === 0xff && b[n - 1] === 0xd9) {
          url = URL.createObjectURL(new Blob([b], { type: "image/jpeg" }));
          const im = new Image(); im.src = url; await im.decode();
          if (alive && ref.current) { ref.current.src = url; if (shown) URL.revokeObjectURL(shown); shown = url; url = null; }
        }
      } catch { /* keep the last good frame */ }
      if (url) URL.revokeObjectURL(url);
      if (alive) setTimeout(tick, Math.max(0, 100 - (performance.now() - t0)));
    };
    tick();
    return () => { alive = false; if (shown) URL.revokeObjectURL(shown); };
  }, [id]);
  return <img ref={ref} alt={alt} className="block aspect-video w-full bg-black object-contain" />;
}

// Clips mode: what a clip played once found, against its label. The one large number is onset → alert (D50).
function Verdict({ c, status, evs = [] }) {
  const head = (chip) => (
    <div className="flex h-10 shrink-0 items-center justify-between border-b border-line px-4"><Label>Verdict</Label>{chip}</div>
  );
  if (!c) return (
    <section className="flex flex-col rounded-md border border-line bg-surface">
      {head(null)}
      <Empty className="flex-1" title="No verdict yet" hint="Play a labelled clip to see expected against detected, and the onset → alert time." />
    </section>
  );
  const done = status === "ended";
  const at = (e) => { const ts = e.alert?.t_stored ?? e.start_ts; return ts && c.t_first ? `${(ts - c.t_first).toFixed(1)} s` : "—"; };
  const hit = evs.find((e) => e.category === c.label);
  const o2a = hit?.alert?.onset_to_alert_ms;
  const [dot, word] = !done ? ["bg-high", "Running"] : !c.label ? ["bg-fg-3", "Unlabelled"]
    : c.label === "normal" ? (evs.length ? ["bg-crit", "False alarm"] : ["bg-ok", "Correct"])
    : hit ? ["bg-ok", "Detected"] : evs.length ? ["bg-high", "Wrong category"] : ["bg-crit", "Missed"];
  const hint = o2a != null ? `Alert at ${at(hit)} in the clip, onset at ${c.onset_s} s`
    : hit ? `Alert at ${at(hit)} in the clip${c.onset_s == null ? "; no labelled onset" : ""}`
    : !c.label ? "Unlabelled clip: no onset to time from"
    : c.label === "normal" ? "Normal clip: no incident to time"
    : done ? "No matching alert" : "Waiting for the alert";
  const top = hit ?? evs[evs.length - 1];
  return (
    <section className="flex flex-col rounded-md border border-line bg-surface">
      {head(<Chip className="border border-line-strong text-fg-2"><Dot className={dot} />{word}</Chip>)}
      <div className="flex flex-1 flex-col gap-4 p-4">
        <div>
          <div className="label">Onset → alert</div>
          <div className="mt-1 font-mono text-20 font-semibold text-fg">{o2a != null ? ms(o2a) : "—"}</div>
          <div className="text-12 text-fg-3">{hint}</div>
        </div>
        <dl className="grid grid-cols-2 gap-4 border-t border-line pt-4">
          <div>
            <dt className="label">Expected</dt>
            <dd className="mt-1 text-13 font-medium text-fg">{c.label ? title(c.label) : "No label"}</dd>
            <dd className="font-mono text-12 text-fg-3">{c.onset_s != null ? `onset ${c.onset_s} s` : "no onset"}</dd>
          </div>
          <div className="min-w-0">
            <dt className="label">Detected</dt>
            {evs.length ? evs.slice(-3).map((e) => (
              <dd key={e.id} className="mt-1 flex items-center gap-2">
                <Dot className={SEV_BG[e.severity]} /><span className="truncate text-13 font-medium text-fg">{title(e.category)}</span>
                <span className="whitespace-nowrap font-mono text-12 text-fg-3">{pc(e.alert?.confidence ?? e.peak_confidence)} · {at(e)}</span>
              </dd>
            )) : <dd className="mt-1 text-13 text-fg-2">{done ? "No incidents" : "Nothing yet"}</dd>}
          </div>
        </dl>
        {top && (top.summary ? <p className="line-clamp-2 text-13 text-fg-2">{top.summary}</p>
          : <div className="space-y-1.5"><Skeleton className="h-3" /><Skeleton className="h-3 w-2/3" /></div>)}
        <div className="mt-auto truncate font-mono text-11 text-fg-3">{c.name} · played once</div>
      </div>
    </section>
  );
}

function Library({ playing, onPlay }) {   // Act 1: one click plays a clip once; it replaces the one playing
  const [clips, setClips] = useState(null);   // null loading · false error
  const [msg, setMsg] = useState("");
  useEffect(() => { getJSON("/api/clips").then(setClips).catch(() => setClips(false)); }, []);
  const play = async (x) => {
    const r = await post("/api/clips/play", { path: x.path });
    setMsg(r.ok ? "" : `Rejected: ${(await r.json()).detail}`);
    onPlay();
  };
  const send = async (f) => {   // upload: plays once, replaces the clip playing
    if (!f) return;
    setMsg(`Uploading ${f.name}…`);
    const r = await fetch(`/api/cameras/upload?name=${encodeURIComponent(f.name)}`, { method: "POST", body: f });
    const j = await r.json();
    setMsg(r.ok ? `${j.id} added: ${j.name}` : `Rejected: ${j.detail}`);
    onPlay();
  };
  const cols = "grid grid-cols-[16px_minmax(0,1fr)_120px_64px_104px] items-center gap-3 px-4";
  return (
    <section onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); send(e.dataTransfer.files[0]); }}
      className="rounded-md border border-line bg-surface">
      <div className="flex h-10 items-center gap-2 border-b border-line px-4">
        <Label>Clip library</Label>
        <span className="font-mono text-11 text-fg-3">{clips ? clips.length : ""}</span>
        <span className={`ml-auto truncate text-12 ${msg.startsWith("Rejected") ? "text-crit" : "text-fg-3"}`}>
          {msg || "One at a time, played once. Drop a video here to upload."}
        </span>
        <label className="inline-flex h-6 shrink-0 cursor-pointer items-center gap-1.5 rounded border border-line-strong px-2 text-12 font-medium text-fg hover:bg-raised focus-within:outline-2 focus-within:outline-accent-fg">
          <input type="file" accept=".mp4,.mov,.avi,.mkv" className="sr-only" onChange={(e) => send(e.target.files[0])} />
          <Ic.Upload size={14} />Upload video
        </label>
      </div>
      {clips === false ? <Empty icon={Ic.Alert} title="Could not load clips" hint="Check the server is running, then reload the page." />
        : clips && !clips.length ? <Empty icon={Ic.Video} title="No clips found" hint="Copy videos into data/demo/ or data/dev/<category>/, or upload one (mp4, mov, avi, mkv, up to 500 MB)." />
        : (
          <div role="list">
            <div className={`${cols} label h-8`}><span /><span>Clip</span><span>Label</span><span>Onset</span><span>Folder</span></div>
            {clips ? clips.map((x) => {
              const on = playing === x.path;
              return (
                <button key={x.path} role="listitem" onClick={() => play(x)} aria-current={on || undefined}
                  className={`${cols} h-9 w-full border-t border-line text-left hover:bg-raised ${on ? "bg-raised" : ""}`}>
                  <Ic.Play size={14} className={on ? "text-accent-fg" : "text-fg-3"} />
                  <span className="truncate font-mono text-12 text-fg">{x.name}</span>
                  <span className="truncate text-13 text-fg-2">{x.label ? title(x.label) : "Unlabelled"}</span>
                  <span className="font-mono text-12 text-fg-3">{x.onset_s != null ? `${x.onset_s} s` : "—"}</span>
                  <span className="truncate font-mono text-12 text-fg-3">{x.folder}</span>
                </button>
              );
            }) : [0, 1, 2, 3].map((i) => <div key={i} className={`${cols} h-9 border-t border-line`}><span /><Skeleton className="h-3" /><Skeleton className="h-3" /><span /><span /></div>)}
          </div>
        )}
    </section>
  );
}

function AddSource({ cams, onDone }) {   // Act 2: devices (iPhone via Continuity, webcams) and phone stream URLs
  const [devs, setDevs] = useState(null);   // null loading · false error
  const [url, setUrl] = useState("");
  const [msg, setMsg] = useState("");
  useEffect(() => { getJSON("/api/devices").then(setDevs).catch(() => setDevs(false)); }, []);
  const running = new Set(cams.map((c) => c.source));
  const add = async (source, label) => {
    const r = await post("/api/cameras", { source, name: label });
    setMsg(r.ok ? "" : `Rejected: ${(await r.json()).detail}`);
    onDone();
  };
  return (
    <section className="flex flex-col rounded-md border border-line bg-surface">
      <div className="flex h-10 shrink-0 items-center border-b border-line px-4"><Label>Add source</Label></div>
      <div className="flex flex-1 flex-col gap-4 p-4">
        <div>
          <div className="label mb-2">Devices</div>
          {devs == null ? <div className="flex gap-2"><Skeleton className="h-8 w-32" /><Skeleton className="h-8 w-28" /></div>
            : devs === false ? <p className="text-12 text-crit">Could not list cameras. Reload the page.</p>
            : !devs.length ? <p className="text-12 text-fg-3">No cameras found. Check camera permission, or add a stream URL.</p>
            : (
              <div className="flex flex-wrap gap-2">
                {devs.map((d) => (
                  <Button key={d.source} disabled={running.has(d.source)} onClick={() => add(d.source, d.name)}>
                    <Ic.Plus size={14} />{d.name}
                  </Button>
                ))}
              </div>
            )}
        </div>
        <form onSubmit={(e) => { e.preventDefault(); if (url.trim()) add(url.trim(), null); }}>
          <label htmlFor="src-url" className="label mb-2 block">Stream URL</label>
          <div className="flex gap-2">
            <input id="src-url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="rtsp://… or http://192.168.43.20:8080/video"
              className="h-8 min-w-0 flex-1 rounded border border-line-strong bg-page px-2 font-mono text-12 text-fg placeholder:text-fg-3" />
            <Button>Add URL</Button>
          </div>
          <p className="mt-1 text-11 text-fg-3">http, https or rtsp</p>
        </form>
        {msg && <p className="text-12 text-crit">{msg}</p>}
      </div>
    </section>
  );
}

function useTop3(e) {   // live alert: top-3 from the SSE message; history: from the event's peak observation
  const [top3, setTop3] = useState(null);
  useEffect(() => {
    if (e.alert) return;
    getJSON(`/api/events/${e.id}`).then((d) => {
      const o = d.observations?.filter((o) => o.probs).sort((a, b) => b.probs[e.category] - a.probs[e.category])[0];
      setTop3(o ? Object.entries(o.probs).sort((a, b) => b[1] - a[1]).slice(0, 3) : false);
    }).catch(() => setTop3(false));
  }, [e.id, e.n_obs]);   // the first observation is stored after the alert
  return e.alert?.top3 ?? top3;
}

const STATUS_WORD = { open: "Open", closed: "Closed", acknowledged: "Acknowledged", dismissed: "Dismissed" };

function Alerts({ feed, load, camName, onOpen, onAck }) {
  if (load === "loading") return (
    <div>{[0, 1, 2].map((i) => (
      <div key={i} className="flex gap-3 border-b border-line px-4 py-3">
        <Skeleton className="h-[54px] w-24" /><div className="flex-1 space-y-2"><Skeleton className="h-3 w-1/2" /><Skeleton className="h-3" /><Skeleton className="h-3 w-3/4" /></div>
      </div>
    ))}</div>
  );
  if (load === "error") return <Empty icon={Ic.Alert} title="Could not load alerts" hint="Check the server is running, then reload the page." />;
  if (!feed.length) return <Empty icon={Ic.Check} title="No alerts" hint="Incidents appear here the moment the model confirms one." />;
  return (
    <ol aria-live="polite" aria-label="Alerts">
      {feed.map((e) => <li key={e.id}><AlertCard e={e} camName={camName(e)} onOpen={onOpen} onAck={onAck} /></li>)}
    </ol>
  );
}

function AlertCard({ e, camName, onOpen, onAck }) {
  const t3 = useTop3(e);
  const thumb = e.keyframe_paths?.[0];
  return (
    <article className={`relative border-b border-line px-4 py-3 hover:bg-surface ${e.alert ? "animate-enter" : ""}`}>
      <span aria-hidden="true" className={`absolute inset-y-3 left-0 w-[3px] rounded-r-sm ${SEV_BG[e.severity] ?? "bg-fg-3"} ${e.status === "open" ? "" : "opacity-40"}`} />
      <div className="flex gap-3">
        {thumb ? <img src={media(thumb)} alt="" className="h-[54px] w-24 shrink-0 rounded bg-raised object-cover" />
          : e.seeded ? <div className="grid h-[54px] w-24 shrink-0 place-items-center rounded bg-raised text-fg-3"><Ic.Video /></div>
          : <Skeleton className="h-[54px] w-24 shrink-0" />}
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline gap-2">
            {/* the title's ::after covers the card, so a click anywhere opens it; Ack sits above it */}
            <button onClick={() => onOpen(e)} className="truncate text-left text-13 font-semibold text-fg after:absolute after:inset-0">{title(e.category)}</button>
            {e.seeded ? <Chip className="border border-line-strong text-fg-3" title="Seeded demo history (E-19)">History</Chip> : null}
            <span className="ml-auto shrink-0 font-mono text-12 text-fg-3">{ist(e.start_ts ?? e.alert?.t_stored)}</span>
          </div>
          <div className="flex items-center gap-2 text-12 text-fg-2">
            <span className="truncate">{camName}</span>
            <span className="whitespace-nowrap font-mono text-fg-3">
              {pc(e.alert?.confidence ?? e.peak_confidence)}{e.alert?.rating ? ` ${e.alert.rating}` : ""}
              {e.alert && e.peak_confidence > e.alert.confidence && ` (peak ${pc(e.peak_confidence)})`}
            </span>
          </div>
          {e.summary ? <p className="mt-1 line-clamp-2 text-13 text-fg-2">{e.summary}</p>
            : <div className="mt-2 space-y-1.5"><Skeleton className="h-3" /><Skeleton className="h-3 w-2/3" /></div>}
        </div>
      </div>
      {t3 !== false && <div className="mt-3"><Top3 t3={t3} /></div>}
      <div className="mt-2 flex h-6 items-center gap-3 whitespace-nowrap font-mono text-11 text-fg-3">
        {e.time_to_alert_ms != null && <span>trigger → alert {ms(e.time_to_alert_ms)}</span>}
        {e.alert?.onset_to_alert_ms != null && <span>onset → alert {ms(e.alert.onset_to_alert_ms)}</span>}
        {e.status === "open" ? <Button size="sm" className="relative z-10 ml-auto font-sans" onClick={() => onAck(e.id)}>Ack</Button>
          : <span className="ml-auto font-sans">{STATUS_WORD[e.status] ?? e.status}</span>}
      </div>
    </article>
  );
}

function EventDialog({ e, camName, onAck, onClose }) {
  const t3 = useTop3(e);
  const close = useRef(null);
  useEffect(() => { close.current?.focus(); }, []);
  const thumb = e.keyframe_paths?.[0];
  const facts = [["Camera", camName(e)], ["Time", `${ist(e.start_ts ?? e.alert?.t_stored)} IST`],
    ["Confidence", `${pc(e.alert?.confidence ?? e.peak_confidence)}${e.alert?.rating ? ` ${e.alert.rating}` : ""}`],
    ["Trigger → alert", ms(e.time_to_alert_ms)], ["Onset → alert", ms(e.alert?.onset_to_alert_ms)], ["Status", STATUS_WORD[e.status] ?? e.status]];
  return (
    <div onClick={onClose} className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4">
      <div role="dialog" aria-modal="true" aria-labelledby="ev-title" onClick={(x) => x.stopPropagation()} data-event-card={e.id}
        className="w-full max-w-[560px] animate-enter overflow-hidden rounded-md border border-line-strong bg-surface shadow-2xl">
        <div className="flex h-12 items-center gap-2 border-b border-line px-4">
          <Dot className={SEV_BG[e.severity] ?? "bg-fg-3"} />
          <h2 id="ev-title" className="text-15 font-semibold">{title(e.category)}</h2>
          <span className={`text-12 ${SEV_TEXT[e.severity] ?? "text-fg-3"}`}>{title(e.severity)}</span>
          <span className="font-mono text-12 text-fg-3">#{e.id}</span>
          {e.seeded ? <Chip className="border border-line-strong text-fg-3">History</Chip> : null}
          <button ref={close} onClick={onClose} aria-label="Close" className="ml-auto grid size-8 place-items-center rounded text-fg-3 hover:bg-raised hover:text-fg"><Ic.X /></button>
        </div>
        {thumb ? <img src={media(thumb)} alt={`Key frame of event ${e.id}`} className="block aspect-video w-full bg-black object-contain" />
          : <div className="grid aspect-video place-items-center bg-page text-12 text-fg-3">{e.seeded ? "Seeded history has no key frame" : "No key frame yet"}</div>}
        <div className="space-y-4 p-4">
          {e.summary ? <p className="text-13 text-fg">{e.summary}</p> : <div className="space-y-1.5"><Skeleton className="h-3" /><Skeleton className="h-3 w-2/3" /></div>}
          {t3 !== false && <Top3 t3={t3} />}
          <dl className="grid grid-cols-3 gap-x-4 gap-y-3 border-t border-line pt-4">
            {facts.map(([k, val]) => <div key={k} className="min-w-0"><dt className="text-11 text-fg-3">{k}</dt><dd className="truncate font-mono text-12 text-fg">{val}</dd></div>)}
          </dl>
        </div>
        {e.status === "open" && (
          <div className="flex justify-end border-t border-line px-4 py-3"><Button variant="primary" onClick={() => onAck(e.id)}>Ack</Button></div>
        )}
      </div>
    </div>
  );
}

// Chat (§7.5): every [#id] is a chip that opens that event; the line under each answer says how it was made.
const how = (h) => (!h ? "" : (h.read_by === "model" ? `question read by the model (${h.read_ms} ms) · ` : "question read by rules · ")
  + (h.mode === "template" ? "template answer"
    : `model answer, ${h.rows} rows, ${h.dropped} sentence${h.dropped === 1 ? "" : "s"} dropped${h.fallback ? " → template" : ""}`));
const SESSION = Math.random().toString(36).slice(2);   // one conversation per page load: follow-ups use the last 3 turns
const SUGGEST = ["Show all tailgating events from camera 2 today", "What incidents happened in the last 10 minutes?",
  "Summarise the incidents in the lobby today", "How many fights were there?"];

function Chat({ onOpen, inputRef }) {
  const [q, setQ] = useState("");
  const [log, setLog] = useState([]);
  const [busy, setBusy] = useState(null);   // the question in flight
  const end = useRef(null);
  useEffect(() => { end.current?.scrollIntoView({ block: "end" }); }, [log, busy]);
  const ask = async (text) => {
    const question = text.trim();
    if (!question || busy) return;
    setBusy(question);
    try {
      const r = await post("/api/chat", { session_id: SESSION, question });
      const a = r.ok ? await r.json() : { answer: `error ${r.status}`, events: [], error: true };
      setLog((l) => [...l, { question, ...a }].slice(-20));
      setQ("");
    } catch {
      setLog((l) => [...l, { question, answer: "Could not reach the server", events: [], error: true }].slice(-20));
    } finally { setBusy(null); }
  };
  return (
    <div className="flex h-full flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        {!log.length && !busy && (
          <div>
            <Empty title="Ask about incidents" hint="Answers come only from stored events. Every #id opens that event." />
            <div className="label mb-2">Try</div>
            <div className="space-y-2">
              {SUGGEST.map((s) => (
                <button key={s} onClick={() => ask(s)} className="block w-full rounded border border-line px-3 py-2 text-left text-13 text-fg-2 hover:bg-surface hover:text-fg">{s}</button>
              ))}
            </div>
          </div>
        )}
        <div className="space-y-6">
          {log.map((a, i) => <Answer key={i} a={a} n={i + 1} onOpen={onOpen} />)}
          {busy && (
            <div>
              <Question text={busy} />
              <div className="space-y-1.5"><Skeleton className="h-3" /><Skeleton className="h-3 w-4/5" /><Skeleton className="h-3 w-1/2" /></div>
            </div>
          )}
        </div>
        <div ref={end} />
      </div>
      <form onSubmit={(x) => { x.preventDefault(); ask(q); }} className="shrink-0 border-t border-line p-3">
        <div className="flex items-center gap-2 rounded border border-line-strong bg-surface pl-3 pr-1 focus-within:border-accent-fg">
          <input ref={inputRef} value={q} onChange={(x) => setQ(x.target.value)} aria-label="Ask about incidents" placeholder="Ask about incidents"
            className="h-9 min-w-0 flex-1 bg-transparent text-13 text-fg outline-none placeholder:text-fg-3" />
          <kbd className="rounded border border-line-strong px-1 font-mono text-11 text-fg-3">/</kbd>
          <Button variant="primary" size="sm" disabled={!!busy || !q.trim()}><Ic.Send size={14} />Ask</Button>
        </div>
      </form>
    </div>
  );
}

const Question = ({ text }) => (
  <div className="mb-2 flex justify-end"><div className="max-w-[85%] rounded-md bg-raised px-3 py-2 text-13 text-fg">{text}</div></div>
);

function Answer({ a, n, onOpen }) {
  const cite = a.answer.split(/(\[#\d+\])/).map((s, i) => {
    const e = /^\[#\d+\]$/.test(s) && a.events.find((ev) => ev.id === +s.slice(2, -1));
    return e ? (
      <button key={i} onClick={() => onOpen(e)} title={`Open event ${e.id}`}
        className="mx-0.5 inline-flex h-5 items-center rounded border border-line-strong bg-surface px-1.5 align-middle font-mono text-11 text-accent-fg hover:bg-raised">#{e.id}</button>
    ) : s;
  });
  return (
    <div data-answer={n}>
      <Question text={a.question} />
      <div className={`whitespace-pre-wrap text-13 leading-6 ${a.error ? "text-crit" : "text-fg"}`}>{cite}</div>
      {a.error && <div className="text-12 text-fg-3">Reload the page (⌘R) and ask again.</div>}
      {a.events?.length > 0 && (   // P5: key frame + IST time per cited event (the brief's "timestamps and key frames")
        <div className="mt-3 flex gap-2 overflow-x-auto pb-1" data-frames>
          {a.events.map((e) => (
            <button key={e.id} onClick={() => onOpen(e)} title={e.summary ?? ""} className="w-28 shrink-0 rounded text-left">
              {e.keyframe_paths?.[0] ? <img src={media(e.keyframe_paths[0])} className="h-[63px] w-28 rounded border border-line bg-raised object-cover" alt="" />
                : <div className="grid h-[63px] w-28 place-items-center rounded border border-line bg-surface text-fg-3" title={e.seeded ? "Seeded history has no key frame" : "No key frame"}><Ic.Video /></div>}
              <div className="mt-1 truncate font-mono text-11 text-fg-2">#{e.id} · {ist(e.start_ts)}</div>
              <div className="truncate text-11 text-fg-3">{title(e.category)} · {e.camera_name}</div>
            </button>
          ))}
        </div>
      )}
      {!a.error && <div className="mt-2 font-mono text-11 text-fg-3" data-how>{how(a.how)} · as of {ist(a.as_of)} IST · {a.latency_ms} ms</div>}
    </div>
  );
}

// Pipeline (FR-15): the newest model call on one camera, stage by stage, then what the model saw and said.
const pretty = (s) => { try { return JSON.stringify(JSON.parse(s), null, 2); } catch { return s; } };

function Pipeline({ cams, traces, m }) {
  const [sel, setSel] = useState(null);
  const newest = cams.filter((c) => traces[c.id]).sort((a, b) => traces[b.id].ts - traces[a.id].ts)[0];
  const c = cams.find((x) => x.id === sel) ?? newest ?? cams[0];
  return (
    <div className="space-y-6 p-4">
      {cams.length > 1 && <Segmented label="Camera" value={c?.id} options={cams.map((x) => [x.id, x.id])} onChange={setSel} />}
      {c ? <Trace c={c} t={traces[c.id]} cm={m?.cameras?.[c.id]} m={m} />
        : <Empty icon={Ic.Video} title="No sources running" hint="Play a clip or add a camera. Every model call is traced here, stage by stage." />}
      <System m={m} />
    </div>
  );
}

function Trace({ c, t, cm, m }) {
  const st = Object.fromEntries((t?.stages ?? []).map((s) => [s.name, s.ms]));
  const vlm = st["prefill → 1st token"] != null || st["1st token → category"] != null
    ? (st["prefill → 1st token"] ?? 0) + (st["1st token → category"] ?? 0) : null;
  const o2a = m?.latency?.onset_to_alert_ms ?? {};
  const n = (x) => (x == null ? "—" : Math.round(x).toLocaleString("en-US"));
  const nodes = [   // numbers only; the unit sits in the sub-label so 1,137 fits a fifth of the rail
    ["Frame", n(cm?.capture_fps), "fps", "Capture rate"],
    ["YOLO", n(cm?.yolo_ms_p50), "ms p50", "YOLO + ByteTrack per frame, p50"],
    ["Gate", n(st["capture → gate"]), "ms", "Frame captured → gate fired, this call (includes detection)"],
    ["VLM", n(vlm), "ms", "Prefill + first token → category known, this call"],
    ["Event", n(st["store (SQLite)"]), "ms", "Event row stored in SQLite, this call"],
  ];
  const total = (t?.stages ?? []).reduce((a, s) => a + s.ms, 0);
  let acc = 0;
  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="truncate text-15 font-semibold">{c.name}</div>
          <div className="font-mono text-12 text-fg-3">{c.id} · {t ? ist(t.ts) : "—"}</div>
          {t && <Chip className="mt-2 border border-line-strong font-mono text-fg-2">{t.trigger}</Chip>}
        </div>
        <div className="shrink-0 text-right">
          <div className="label">Frame → category</div>
          <div className="font-mono text-20 font-semibold">{ms(t?.model_tta_ms)}</div>
          <div className="font-mono text-11 text-fg-3" title="Never quote the model time alone (D50)">onset → alert p50 {o2a.n ? ms(o2a.p50) : "—"}</div>
        </div>
      </div>

      <ol className="grid grid-cols-5 rounded-md border border-line bg-surface" aria-label="Pipeline stages">
        {nodes.map(([k, val, sub, tip], i) => (
          <li key={k} title={tip} className={`relative min-w-0 px-2 py-3 ${i ? "border-l border-line" : ""}`}>
            <div className="label">{k}</div>
            <div className="mt-1 truncate font-mono text-13 text-fg">{val}</div>
            <div className="truncate text-11 text-fg-3">{sub}</div>
            {i < 4 && (
              <span aria-hidden="true" className="absolute -right-2 top-1/2 z-10 grid size-4 -translate-y-1/2 place-items-center rounded-full border border-line bg-surface text-fg-3">
                <Ic.Chevron size={10} />
              </span>
            )}
          </li>
        ))}
      </ol>

      <div className="rounded-md border border-line bg-surface p-3">
        <div className="mb-3 flex items-baseline justify-between"><Label>Trace</Label><span className="font-mono text-11 text-fg-3">{t ? `${ms(total)} total` : ""}</span></div>
        {t ? (
          <>
            <div className="space-y-2">
              {t.stages.map((s) => {
                const left = total ? (acc / total) * 100 : 0, w = total ? Math.max((s.ms / total) * 100, 0.75) : 0;
                acc += s.ms;
                return (
                  <div key={s.name} className="grid grid-cols-[128px_minmax(0,1fr)_64px] items-center gap-2">
                    <span className="truncate text-12 text-fg-2">{s.name}</span>
                    <div className="relative h-3 rounded-sm bg-page">
                      <div style={{ left: `${left}%`, width: `${w}%` }}
                        className={`absolute inset-y-0 rounded-sm ${s.name === "1st token → category" ? "bg-fg" : "bg-fg-3"}`} />
                    </div>
                    <span className="whitespace-nowrap text-right font-mono text-12 text-fg">{ms(s.ms)}</span>
                  </div>
                );
              })}
            </div>
            <div className="ml-[136px] mr-[72px] mt-2 flex justify-between border-t border-line pt-1 font-mono text-11 text-fg-3"><span>0</span><span>{ms(total)}</span></div>
          </>
        ) : <Empty className="py-4" title="Waiting for the first model call" hint="The gate wakes the model on motion; baselines run when the scene changes." />}
      </div>

      {t && (
        <div className="overflow-hidden rounded-md border border-line bg-surface">
          <div className="flex h-10 items-center border-b border-line px-3"><Label>Model input</Label><span className="ml-auto font-mono text-11 text-fg-3">mosaic · letterboxed</span></div>
          <img src={t.mosaic_url} alt="Mosaic of recent frames sent to the VLM" className="block w-full bg-black" />
          <div className="space-y-3 border-t border-line p-3">
            <div><div className="label mb-1">Hints</div><p className="text-12 text-fg-2">{t.hints || "None"}</p></div>
            <div>
              <div className="label mb-1">Raw VLM output</div>
              <pre className="max-h-48 overflow-auto whitespace-pre-wrap break-words rounded border border-line bg-page p-2 font-mono text-11 text-fg-2">{pretty(t.raw_json)}</pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function System({ m }) {
  const x = m?.vlm ?? {}, o2a = m?.latency?.onset_to_alert_ms ?? {}, s2c = m?.latency?.store_to_card_ms ?? {};
  const rows = [
    ["GPU duty (60 s)", v(x.gpu_duty_pct, "%"), "Share of the last 60 s the model was busy. Target ≤ 60 % average with 3 cameras."],
    ["Onset → alert", o2a.n ? `${ms(o2a.last)} · p50 ${o2a.p50}` : "—",
      "Labelled incident onset in the clip → alert (§12). Only for labelled clips played once (uploads, bench/labels.csv); live onset is measured from 240 fps phone video."],
    ["Model time-to-alert p95", ms(x.alert_p95_ms), "Newest frame captured → category known, p95 over all calls. Never quoted alone (D50)."],
    ["VLM call p50 / p95", `${v(x.p50_ms)} / ${v(x.p95_ms)} ms`],
    ["Store → card p95", s2c.n ? `${ms(s2c.p95)} · n ${s2c.n}` : "—",
      "Event row stored → card painted in this browser; budget ≤ 100 ms. Valid only when the browser runs on the server machine (it compares the two clocks); readings from other devices are ignored.",
      s2c.p95 > 100],
    ["Queue", v(x.queue_depth)],
    ["Calls", v(x.calls_total)],
    ["Preempted", v(x.preemptions)],
    ["Baselines skipped", v(x.baselines_skipped), "Baseline calls skipped because the scene had not changed (D42)."],
    ["Vetoes", v(x.vetoes), "Detector cross-check vetoes (E-7)."],
    ["VLM errors", v(x.errors), "The server log prints each [vlm_error] line.", x.errors > 0],
    ["Memory", v(m?.system?.mem_used_pct, "%")],
  ];
  return (
    <div>
      <Label className="mb-2">System</Label>
      <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-md border border-line bg-line">
        {rows.map(([k, val, tip, bad]) => (
          <div key={k} title={tip} className="bg-surface px-3 py-2">
            <dt className="truncate text-11 text-fg-3">{k}</dt>
            <dd className={`truncate font-mono text-13 ${bad ? "text-crit" : "text-fg"}`}>{val}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
