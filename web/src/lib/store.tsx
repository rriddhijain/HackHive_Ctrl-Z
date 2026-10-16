"use client";
// The one client store (CONTRACT §2, §3.1, §4.1). Lives in the root layout, so the SSE connection, the event store,
// metrics, traces, the chat log and SESSION, sound arming, the Pipeline pick and the theme survive tab switches.
import { createContext, useContext, useEffect, useMemo, useRef, useState, type ReactNode, type RefObject } from "react";
import { flushSync } from "react-dom";
import { usePathname, useRouter } from "next/navigation";
import { api, ApiError } from "./api";
import { name as fmtName } from "./format";
import { arm, beep } from "./sound";
import type { AlertMsg, Camera, ChatEntry, Device, Event, Metrics, Mode, Slot, Trace } from "./types";

/** One conversation per page load: follow-ups use the last 3 turns server-side (B-69). */
const SESSION = Math.random().toString(36).slice(2);
const LOG_MAX = 20;

export type Load = "loading" | "ok" | "error";
export type Theme = "dark" | "light";
export type Hours = 1 | 8 | 24;

export interface Store {
  // state
  cams: Camera[];
  events: Record<number, Event>;
  evLoad: Load;
  sound: boolean;
  /** null loading · false error · list (fetched while on /live/, B-44). */
  devices: Device[] | null | false;
  chat: ChatEntry[];
  /** The question in flight, or null. */
  busy: string | null;
  hours: Hours;
  theme: Theme;
  pick: string | null;
  /** The mode a confirm dialog is asking to switch to (§4.2), or null. */
  gate: Mode | null;
  session: string;
  askRef: RefObject<HTMLInputElement | null>;
  // derived
  mode: Mode | undefined;
  /** Mode and the camera list have both loaded: the §4.2 switch-or-confirm decision is safe to make. */
  ready: boolean;
  feed: Event[];
  nOpen: number;
  anyOpenCritical: boolean;
  notifications: Event[];
  camName: (e: Pick<Event, "camera_id" | "camera_name">) => string;
  camEvents: (camId: string) => Event[];
  hot: (camId: string) => Event | undefined;
  camStatus: (c: Camera) => string;
  camInSlot: (slot: Slot) => Camera | undefined;
  overflow: Camera[];
  // actions
  loadCams: () => Promise<void>;
  ack: (id: number) => Promise<void>;
  dismiss: (id: number) => Promise<void>;
  switchMode: (k: Mode) => Promise<void>;
  requestMode: (k: Mode) => void;
  confirmGate: () => void;
  cancelGate: () => void;
  playClip: (path: string, slot: Slot) => Promise<string>;
  uploadClip: (file: File, slot: Slot) => Promise<string>;
  addSource: (source: number | string, name: string | null, slot: Slot) => Promise<string>;
  removeSource: (id: string) => Promise<void>;
  rescan: () => void;
  ask: (question: string) => Promise<boolean>;
  handover: () => Promise<void>;
  setHours: (h: Hours) => void;
  armSound: () => void;
  toggleTheme: () => void;
  setPick: (id: string | null) => void;
  openEvent: (e: Event | number) => void;
  pushNotification: (id: number) => void;
  closeNotification: (id: number) => void;
  /** Objects events were opened from (chat payloads), by id: the report's second data source (§4.6). */
  opened: Record<number, Event>;
}

/** The values that change every second (metrics, traces, connection): a second context, so alert lists don't re-render on each tick. */
export interface Live {
  m: Metrics | null;
  traces: Record<string, Trace>;
  conn: boolean;
}

const Ctx = createContext<Store | null>(null);
const LiveCtx = createContext<Live | null>(null);

export function useStore(): Store {
  const s = useContext(Ctx);
  if (!s) throw new Error("useStore outside <StoreProvider>");
  return s;
}

export function useLive(): Live {
  const s = useContext(LiveCtx);
  if (!s) throw new Error("useLive outside <StoreProvider>");
  return s;
}

const rejected = (e: unknown) => `Rejected: ${e instanceof ApiError ? e.detail : "Could not reach the server"}`;
const strip = ({ observations: _o, ...e }: Event & { observations?: unknown }): Event => e;

export function StoreProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [cams, setCams] = useState<Camera[]>([]);
  const [events, setEvents] = useState<Record<number, Event>>({});
  const [evLoad, setEvLoad] = useState<Load>("loading");
  const [m, setM] = useState<Metrics | null>(null);
  const [mode, setMode] = useState<Mode | undefined>(undefined);
  const [stat, setStat] = useState<Record<string, string>>({});   // camera id → status, changes only when one does
  const [camsReady, setCamsReady] = useState(false);
  const [traces, setTraces] = useState<Record<string, Trace>>({});
  const [conn, setConn] = useState(false);
  const [sound, setSound] = useState(false);
  const [devices, setDevices] = useState<Device[] | null | false>(null);
  const [chat, setChat] = useState<ChatEntry[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [hours, setHours] = useState<Hours>(8);
  const [theme, setTheme] = useState<Theme>("dark");
  const [pick, setPick] = useState<string | null>(null);
  const [gate, setGate] = useState<Mode | null>(null);
  const [highIds, setHighIds] = useState<number[]>([]);
  const [closed, setClosed] = useState<number[]>([]);
  const [opened, setOpened] = useState<Record<number, Event>>({});
  const askRef = useRef<HTMLInputElement | null>(null);

  // Latest values for the stable actions below.
  const ref = useRef({ cams, mode, hours, busy });
  ref.current = { cams, mode, hours, busy };

  const actions = useMemo(() => {
    const merge = (id: number, patch: Partial<Event>) => setEvents((s) => ({ ...s, [id]: { ...s[id], ...patch } as Event }));
    const loadCams = () => api.cameras().then((c) => { setCams(c); setCamsReady(true); }).catch(() => {});   // keep the last list (B-2)
    const mergeEvents = (rows: Event[]) => setEvents((s) => Object.fromEntries([...rows.map((e) => [e.id, e] as const), ...Object.entries(s)]));
    const loadEvents = () => {
      setEvLoad("loading");
      return api.events(50).then((rows) => { mergeEvents(rows); setEvLoad("ok"); }).catch(() => setEvLoad("error"));
    };
    const switchMode = async (k: Mode) => {   // B-10: stops every source of either mode; history stays
      if (k === ref.current.mode) return;
      try { await api.setMode(k); } catch { /* no error handling (old behaviour) */ }
      setMode(k);
      setM((x) => (x ? { ...x, mode: k } : x));
      await loadCams();
    };
    const pushChat = (e: ChatEntry) => setChat((l) => [...l, e].slice(-LOG_MAX));
    const scan = () => { api.devices().then(setDevices).catch(() => setDevices(false)); };
    return {
      merge, loadEvents, loadCams, switchMode, scan,
      ack: async (id: number) => { try { const e = strip(await api.ack(id)); merge(e.id, e); } catch { /* silent (B-59) */ } },
      dismiss: async (id: number) => {   // FR-25: hidden from every list, counted in Report
        try {
          const e = strip(await api.dismiss(id));
          merge(e.id, e);
          const q = new URLSearchParams(window.location.search).get("id");
          if (window.location.pathname.startsWith("/alerts") && q === String(id)) router.push("/alerts/");
        } catch { /* silent */ }
      },
      requestMode: (k: Mode) => {   // §4.2: switch at once when nothing is listed, else confirm first
        const { mode: x, cams: c } = ref.current;
        if (!x || x === k) return;
        if (!c.length) void switchMode(k);
        else setGate(k);
      },
      playClip: async (path: string, slot: Slot) => {
        try { await api.playClip(path, slot); return ""; } catch (e) { return rejected(e); } finally { void loadCams(); }
      },
      uploadClip: async (file: File, slot: Slot) => {
        try { const j = await api.upload(file, slot); return `${j.id} added: ${j.name}`; } catch (e) { return rejected(e); } finally { void loadCams(); }
      },
      addSource: async (source: number | string, name: string | null, slot: Slot) => {
        try { await api.addSource(source, name, slot); return ""; } catch (e) { return rejected(e); } finally { void loadCams(); }
      },
      removeSource: async (id: string) => { try { await api.removeSource(id); } catch { /* none (B-24) */ } await loadCams(); },
      ask: async (text: string) => {   // B-71; resolves true when the caller should clear the input
        const question = text.trim();
        if (!question || ref.current.busy) return false;
        setBusy(question); ref.current.busy = question;
        try {
          const a = await api.chat(SESSION, question);
          pushChat({ question, ...a });
          return true;
        } catch (e) {
          if (e instanceof ApiError) { pushChat({ question, answer: `error ${e.status}`, events: [], error: true }); return true; }
          pushChat({ question, answer: "Could not reach the server", events: [], error: true });
          return false;
        } finally { setBusy(null); ref.current.busy = null; }
      },
      handover: async () => {   // B-76 (FR-17): incidents first, follow-ups, then notable normal activity
        const h = ref.current.hours;
        const question = `Shift handover · last ${h} h · all cameras`;
        if (ref.current.busy) return;
        setBusy(question); ref.current.busy = question;
        try {
          const d = await api.digest(h);
          const parts = [d.headline, d.narrative];
          if (d.incidents.length) parts.push("Incidents, most severe first:\n" + d.incidents.slice(0, 15).map((x) => x.line).join("\n")
            + (d.incidents.length > 15 ? `\n… and ${d.incidents.length - 15} more` : ""));
          if (d.activity.length) parts.push("Notable normal activity:\n" + d.activity.map((c) => `${c.camera}: ${c.notes.join(" · ")}`).join("\n"));
          pushChat({ question, answer: parts.join("\n\n"), events: d.events, how: d.how, as_of: d.as_of, latency_ms: d.latency_ms });
        } catch {
          pushChat({ question, answer: "Could not build the handover report", events: [], error: true });
        } finally { setBusy(null); ref.current.busy = null; }
      },
      armSound: () => { arm(); setSound(true); },
      toggleTheme: () => setTheme((t) => {
        const next: Theme = t === "dark" ? "light" : "dark";
        document.documentElement.dataset.theme = next;
        try { localStorage.setItem("hh-theme", next); } catch { /* private window */ }
        return next;
      }),
      openEvent: (e: Event | number) => {
        const id = typeof e === "number" ? e : e.id;
        if (typeof e !== "number") setOpened((o) => ({ ...o, [id]: e }));
        router.push(`/alerts/?id=${id}`);
      },
      pushNotification: (id: number) => setHighIds((h) => (h.includes(id) ? h : [...h, id])),
      closeNotification: (id: number) => setClosed((c) => (c.includes(id) ? c : [...c, id])),
    };
  }, [router]);

  // Boot (B-1): cameras, events, one EventSource for the life of the page.
  useEffect(() => {
    const { merge, loadCams, loadEvents } = actions;
    void loadCams();
    void loadEvents();
    const es = new EventSource("/sse");
    const on = <T,>(t: string, f: (x: T) => void) => es.addEventListener(t, (e) => f(JSON.parse((e as MessageEvent).data)));
    // After a lost connection the server may have restarted and reset its live tables, reusing event ids: drop
    // everything keyed by id and reload, so a new event never merges into a stale one.
    let lost = false;
    es.onopen = () => {
      setConn(true);
      if (!lost) return;
      lost = false;
      setEvents({}); setClosed([]); setHighIds([]); setOpened({});
      void loadEvents(); void loadCams();
    };
    es.onerror = () => { setConn(false); lost = true; };
    let camKeys = "";
    on<Metrics>("metrics", (x) => {
      const cs = Object.entries(x.cameras);
      const k = cs.map(([id, c]) => id + c.status).join();   // ids or a status changed
      if (k !== camKeys) { camKeys = k; setStat(Object.fromEntries(cs.map(([id, c]) => [id, c.status]))); void loadCams(); }
      setMode(x.mode);
      setM(x);
    });
    on<AlertMsg>("alert", (a) => {
      flushSync(() => {   // commit the card and the notification now, then measure after the paint (§4.4)
        merge(a.event_id, { id: a.event_id, alert: a, camera_id: a.camera_id, category: a.category, severity: a.severity,
          peak_confidence: a.confidence, time_to_alert_ms: a.trigger_to_alert_ms, status: "open" });
        if (a.severity === "high") setHighIds((h) => [...h, a.event_id]);
      });
      requestAnimationFrame(() => setTimeout(() => api.uiLatency(a.event_id, performance.timeOrigin + performance.now() - a.t_stored * 1000), 0));
      if (a.severity === "critical") beep();   // silent until armed (B-60)
    });
    for (const t of ["event_open", "event_update", "event_close"]) on<Event>(t, (e) => merge(e.id, e));
    on<Trace>("trace", (tr) => setTraces((s) => ({ ...s, [tr.camera_id]: tr })));
    on("camera_status", () => void loadCams());
    // the observation event is ignored: the Now line comes from metrics
    return () => es.close();
  }, [actions]);

  // Theme: the head script already applied ?theme= / localStorage before paint; mirror it into state.
  useEffect(() => { setTheme(document.documentElement.dataset.theme === "light" ? "light" : "dark"); }, []);

  // Devices (B-44): fetched on entering Live and on every window focus while there.
  const onLive = pathname?.startsWith("/live") ?? false;
  useEffect(() => {
    if (!onLive) return;
    actions.scan();
    window.addEventListener("focus", actions.scan);
    return () => window.removeEventListener("focus", actions.scan);
  }, [onLive, actions]);

  const value = useMemo<Store>(() => {
    const all = Object.values(events);
    const feed = all.filter((e) => e.status !== "dismissed").sort((a, b) => b.id - a.id).slice(0, 50);
    const camEvents = (id: string) => all.filter((e) => e.camera_id === id).sort((a, b) => a.id - b.id);
    const notifications = feed.filter((e) => !closed.includes(e.id) && e.status !== "acknowledged" && (
      (e.severity === "critical" && (e.alert || e.status === "open")) || highIds.includes(e.id)));
    return {
      cams, events, evLoad, sound, devices, chat, busy, hours, theme, pick, gate, opened,
      session: SESSION, askRef,
      mode,
      ready: mode !== undefined && camsReady,
      feed,
      nOpen: feed.filter((e) => e.status === "open").length,
      anyOpenCritical: feed.some((e) => e.status === "open" && e.severity === "critical"),
      notifications,
      camName: (e) => e.camera_name ?? cams.find((c) => c.id === e.camera_id)?.name ?? fmtName(e.camera_id),
      camEvents,
      hot: (id) => [...camEvents(id)].reverse().find((e) => e.status === "open" && (e.severity === "critical" || e.severity === "high")),
      camStatus: (c) => stat[c.id] ?? c.status,
      camInSlot: (k) => cams.find((c) => c.slot === k),
      overflow: cams.filter((c) => c.slot == null),
      loadCams: actions.loadCams,
      ack: actions.ack,
      dismiss: actions.dismiss,
      switchMode: actions.switchMode,
      requestMode: actions.requestMode,
      confirmGate: () => { if (gate) void actions.switchMode(gate); setGate(null); },
      cancelGate: () => setGate(null),
      playClip: actions.playClip,
      uploadClip: actions.uploadClip,
      addSource: actions.addSource,
      removeSource: actions.removeSource,
      rescan: actions.scan,
      ask: actions.ask,
      handover: actions.handover,
      setHours,
      armSound: actions.armSound,
      toggleTheme: actions.toggleTheme,
      setPick,
      openEvent: actions.openEvent,
      pushNotification: actions.pushNotification,
      closeNotification: actions.closeNotification,
    };
  }, [cams, events, evLoad, mode, camsReady, stat, sound, devices, chat, busy, hours, theme, pick, gate, opened, highIds, closed, actions]);
  const live = useMemo<Live>(() => ({ m, traces, conn }), [m, traces, conn]);

  return <Ctx.Provider value={value}><LiveCtx.Provider value={live}>{children}</LiveCtx.Provider></Ctx.Provider>;
}

/** An event for the report (§4.6): store entry over the object it was opened from, else GET /api/events/{id}. */
export function useEvent(id: number | null): { event: Event | undefined; state: "none" | "loading" | "ok" | "missing" | "error" } {
  const { events, opened } = useStore();
  const known = id != null && (events[id] || opened[id]) ? ({ ...opened[id], ...events[id] } as Event) : undefined;
  const [fetched, setFetched] = useState<{ id: number; e: Event | null | false } | null>(null);   // null 404 · false other failure
  useEffect(() => {
    if (id == null || known) return;
    let alive = true;
    api.event(id).then((d) => alive && setFetched({ id, e: strip(d) })).catch((err) => alive && setFetched({ id, e: err instanceof ApiError && err.status === 404 ? null : false }));
    return () => { alive = false; };
  }, [id, !!known]); // eslint-disable-line react-hooks/exhaustive-deps
  if (id == null) return { event: undefined, state: "none" };
  if (known) return { event: known, state: "ok" };
  if (fetched?.id !== id) return { event: undefined, state: "loading" };
  return fetched.e ? { event: fetched.e, state: "ok" } : { event: undefined, state: fetched.e === null ? "missing" : "error" };
}
