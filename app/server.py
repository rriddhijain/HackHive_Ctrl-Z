"""HTTP API + SSE + MJPEG for the dashboard (SPEC §9, §9.1, §9.2); serves the built web/ bundle at "/" (offline).

  uv run python -m app.server                 http://localhost:8000; boots in Clips mode with nothing running (P3b)
  uv run python -m app.server --selfcheck     self-check: real pipeline on the sample clip, every endpoint + SSE

Demo modes (P3b): Clips (Act 1) plays ONE playlist clip or upload at a time, once, at real-time speed; Live (Act 2)
runs devices and stream URLs side by side. Switching stops every source; event/observation history is never cleared.

The pipeline's emit() runs on its threads (the alert inside the streaming VLM call), so it only stamps, encodes and
hands the message to the event loop; it never blocks the model.
"""
import asyncio
import base64
import csv
import io
import json
import os
import re
import sys
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

import psutil
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import Response
from fastapi.sse import EventSourceResponse, ServerSentEvent
from fastapi.staticfiles import StaticFiles

from app import chat as chatbot
from app.config import CFG, ROOT
from app.ingest import source_type
from app.notify import Notifier
from app.pager import Pager
from app.pipeline import Pipeline, load_labels, ms, pct
from app.scheduler import persons
from scripts.list_cameras import names as device_names

DATA, DIST = ROOT / "data", ROOT / "web" / "dist"
UPLOAD_EXT = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".webm", ".mpg", ".mpeg", ".wmv", ".flv", ".3gp", ".ts", ".mts", ".m2ts"}   # FR-5; D86: any container OpenCV's FFmpeg reads (a judge's file)
UPLOAD_MAX = 500 * 1024 * 1024
R = CFG["events"]["rating"]

P: Pipeline = None
LOOP: asyncio.AbstractEventLoop = None
SUBS: set[asyncio.Queue] = set()
LAST_OBS, MOSAICS, O2A, S2C = {}, {}, [], []      # camera -> newest observation / mosaic jpeg; latency samples (ms)
LABELS = load_labels()
NEXT_ID, MODE = [0], ["clips"]
SLOTS: dict[str, int] = {}                        # camera id -> dashboard column 1..N_SLOTS (v1.21, D82)
N_SLOTS = 3
SRC_LOCK = threading.Lock()                       # one source change at a time (double clicks, two tabs)


def rating(c):
    return "High" if c >= R["high"] else "Medium" if c >= R["medium"] else "Low"


def clean(ev):
    return {k: v for k, v in ev.items() if not k.startswith("_")}


def send(kind, data):
    msg = ServerSentEvent(raw_data=json.dumps(data, default=str), event=kind)
    for q in list(SUBS):
        if q.qsize() < 500:                       # a stalled tab drops messages instead of growing memory
            q.put_nowait(msg)


def emit(kind, d):
    """Pipeline hook (pipeline threads) -> SSE messages (§9.2)."""
    try:
        out = []
        if kind == "alert":                       # emitted right after the event row is INSERTed
            t_stored, cam = time.time(), P.cams.get(d["camera_id"])
            if NOTIFY is not None:                # D89: queue put only; phones never delay an alert
                NOTIFY.alert(d, cam.name if cam else None)
            label, onset = LABELS.get(Path(str(cam.source)).name, (None, None)) if cam else (None, None)
            o2a = (ms(cam.t_first + onset, d["_t_alert"]) if cam and not cam.loop and cam.t_first
                   and onset is not None and label == d["category"] else None)   # §12, labelled clip played once
            if o2a is not None:
                O2A.append(o2a)
            out = [("alert", {"event_id": d["id"], "camera_id": d["camera_id"], "category": d["category"],
                              "severity": d["severity"], "confidence": round(d["peak_confidence"], 3),
                              "rating": rating(d["peak_confidence"]),
                              "top3": [[k, round(v, 3)] for k, v in d["_probs"]],
                              "trigger_to_alert_ms": d["time_to_alert_ms"], "t_stored": t_stored,
                              "onset_to_alert_ms": o2a}),
                   ("event_open", clean(d))]
        elif kind in ("event_update", "event_close"):
            out = [(kind, clean(d))]
        elif kind == "observation":
            LAST_OBS[d["camera_id"]] = d
            out = [(kind, d)]
        elif kind == "trace":
            t, cam = d["timing"], d["camera_id"]
            MOSAICS[cam] = base64.b64decode(d["mosaic_b64"])
            stages = [("capture → gate", t.get("t_capture"), t.get("t_gate")),
                      ("queue", d["created"], t.get("t_vlm_start")),
                      ("prefill → 1st token", t.get("t_vlm_start"), t.get("t_first_token")),
                      ("1st token → category", t.get("t_first_token"), t.get("t_category")),
                      ("category → done", t.get("t_category"), t.get("t_vlm_done")),
                      ("store (SQLite)", t.get("t_vlm_done"), t.get("t_db_write"))]
            out = [("trace", {"camera_id": cam, "trigger": d["trigger"], "ts": t.get("t_capture"),
                              "stages": [{"name": n, "ms": ms(a, b)} for n, a, b in stages if ms(a, b) is not None],
                              "model_tta_ms": ms(t.get("t_capture"), t.get("t_category")),
                              "mosaic_url": f"/media/mosaics/{cam}.jpg?t={t.get('t_capture')}",
                              "hints": d["hints"], "raw_json": d["raw_json"]})]
        for k, v in out:
            LOOP.call_soon_threadsafe(send, k, v)
    except Exception as e:                        # never break the model call over a UI message
        print(f"[server emit] {kind}: {e!r}", flush=True)


def now_line(cid, det):
    """FR-16: newest model summary, or between summaries a detector template (D42 stops most baselines at the category)."""
    o = LAST_OBS.get(cid)
    if o and o.get("summary"):
        return {"text": o["summary"], "ts": o["ts"], "source": "model"}
    if not det or not det.buffer:
        return None
    entry = det.buffer[-1]
    n = len(persons(entry))
    cats = [cat for cam, cat in list(P.events.open) if cam == cid]
    return {"text": f"{n} {'person' if n == 1 else 'people'}, {', '.join(cats) + ' open' if cats else 'no incident'}",
            "ts": entry[0], "source": "detector"}


def lat(xs):
    xs = list(xs)
    return {"last": xs[-1] if xs else None, "p50": pct(xs, .5), "p95": pct(xs, .95), "n": len(xs)}


def metrics():
    """§9.1 (+ v1.9: per-camera people/now, latency block)."""
    calls = list(P.calls)
    full = [c for c in calls if c.get("call_ms") is not None]
    p1 = [c for c in full if c["prio"] == 1]
    cams = {}
    for cid, cam in list(P.cams.items()):
        det = P.dets.get(cid)
        s = det.stats() if det else {}
        cams[cid] = {"capture_fps": round(cam.fps(), 1), "det_fps": s.get("det_fps"), "yolo_ms_p50": s.get("yolo_ms_p50"),
                     "keep_up": s.get("keep_up"), "status": cam.status,
                     "people": len(persons(det.buffer[-1])) if det and det.buffer else 0, "now": now_line(cid, det)}
    return {"mode": MODE[0], "cameras": cams,
            "vlm": {"model": CFG["vlm"]["model"], "p50_ms": pct([c["call_ms"] for c in full], .5),
                    "p95_ms": pct([c["call_ms"] for c in full], .95),
                    "alert_p95_ms": pct([c["model_tta_ms"] for c in full], .95),   # model time-to-alert (D50)
                    "queue_depth": len(P.arb.waiting()), "calls_total": len(calls),
                    "gate_yield_pct": round(100 * sum(c["category"] != "normal" for c in p1) / len(p1), 1) if p1 else None,
                    "cache_hit_tokens": None, "preemptions": sum(c.get("stopped") == "cancelled" for c in calls),
                    "errors": P.vlm_errors, "gpu_duty_pct": round(100 * P.arb.duty(60), 1),
                    "baselines_skipped": P.sched.skipped, "vetoes": sum(v["p_before"] >= 0.3 for v in P.vetoes)},
            "latency": {"onset_to_alert_ms": lat(O2A), "store_to_card_ms": lat(S2C[-200:])},
            "system": {"mem_used_pct": psutil.virtual_memory().percent, "uptime_s": round(time.time() - P.t0)}}


@asynccontextmanager
async def lifespan(_):
    global LOOP
    LOOP = asyncio.get_running_loop()
    for d in ("keyframes", "thumbs", "uploads"):
        (DATA / d).mkdir(parents=True, exist_ok=True)

    async def tick():                             # §9.2 metrics every 1 s
        while True:
            await asyncio.sleep(1)
            if SUBS:
                send("metrics", metrics())
    task = asyncio.create_task(tick())
    yield
    task.cancel()


app = FastAPI(title="HackHive", lifespan=lifespan)


@app.get("/sse", response_class=EventSourceResponse)
async def sse(request: Request):
    q = asyncio.Queue()
    SUBS.add(q)
    try:
        yield ServerSentEvent(raw_data=json.dumps(metrics()), event="metrics")
        while not await request.is_disconnected():
            try:
                yield await asyncio.wait_for(q.get(), 5)
            except TimeoutError:
                pass
    finally:
        SUBS.discard(q)


def notify(kind, data):                           # SSE from a worker thread: asyncio queues aren't thread-safe
    LOOP.call_soon_threadsafe(send, kind, data)


def need(mode):
    if MODE[0] != mode:
        raise HTTPException(409, f"switch to {mode} mode first")


def stop_all():
    """Stop every source, then wait (≤ 1.5 s in all) for the capture threads to release their devices."""
    stop([c.id for c in P.cams.values()])


def stop(ids):
    cams = [P.cams[i] for i in ids if i in P.cams]
    for cam in cams:
        P.remove_camera(cam.id)
        SLOTS.pop(cam.id, None)
        notify("camera_status", {"camera_id": cam.id, "status": "down"})
    deadline = time.time() + 1.5
    for cam in cams:
        cam.join(max(0, deadline - time.time()))


def want_slot(v):
    """A requested dashboard column: None (not given) or 1..N_SLOTS, else 400."""
    if v is None:
        return None
    if type(v) is not int or not 1 <= v <= N_SLOTS:
        raise HTTPException(400, f"slot must be 1-{N_SLOTS}")
    return v


def in_slot(slot):
    return [cid for cid, k in SLOTS.items() if k == slot and cid in P.cams]


def start(c, loop):
    NEXT_ID[0] += 1                               # ids never reused: history keeps pointing at the right camera
    cid = f"cam{NEXT_ID[0]}"
    cam = P.add_camera(c | {"id": cid}, loop=loop)
    return {"id": cid, "name": c["name"], "status": cam.status}


def play_clip(path, name, slot=None):
    """Clips mode, played once. v1.21 (D82): up to N_SLOTS clips side by side, one per dashboard column; a clip
    started in a slot replaces the one there. No slot = the original one-at-a-time behaviour: every clip stops and
    this one plays in slot 1. Measured cost: 3 busy clips at once push GPU duty > 90 % and alerts to seconds (P2b)."""
    with SRC_LOCK:
        need("clips")
        stop(in_slot(slot)) if slot else stop_all()
        out = start({"name": name, "source": path}, loop=False)
        SLOTS[out["id"]] = slot or 1
        return out | {"slot": slot or 1}


def clip_list():
    files = sorted(DATA.glob("demo/*")) + sorted(DATA.glob("dev/*/*"))
    return [{"path": str(f.relative_to(ROOT)), "name": f.name, "folder": str(f.parent.relative_to(DATA)),
             "label": LABELS.get(f.name, (None, None))[0], "onset_s": LABELS.get(f.name, (None, None))[1]}
            for f in files if f.suffix.lower() in UPLOAD_EXT and f.is_file()]


@app.post("/api/mode")
def set_mode(body: dict):
    """Clips | Live. Switching stops and releases every source; history is kept (chat spans both acts)."""
    if body.get("mode") not in ("clips", "live"):
        raise HTTPException(400, "mode must be clips or live")
    t = time.time()
    with SRC_LOCK:
        if body["mode"] != MODE[0]:
            stop_all()
            MODE[0] = body["mode"]
    return {"mode": MODE[0], "switch_ms": ms(t, time.time())}


@app.get("/api/clips")
def clips():
    return clip_list()


@app.post("/api/clips/play")
def play(body: dict):
    clip = next((c for c in clip_list() if c["path"] == body.get("path")), None)   # playlist files only
    if not clip:
        raise HTTPException(400, "not a playlist clip")
    return play_clip(clip["path"], clip["name"], want_slot(body.get("slot")))


@app.get("/api/devices")
def devices():
    """Camera indices with names (scripts/list_cameras.py), plus the stream URLs set in config.yaml (E-15)."""
    found = [{"source": i, "name": "iPhone (live)" if "iphone" in n.lower() else n}
             for i, n in device_names().items()]
    return found + [{"source": c["source"], "name": c["name"]} for c in CFG["cameras"]
                    if source_type(c["source"]) == "stream"]


@app.post("/api/cameras")
def add_source(body: dict):
    """Live mode: a device index or an http/https/rtsp URL. File paths and every other scheme are rejected."""
    src = body.get("source")
    url = urlparse(src) if isinstance(src, str) else None
    if not ((type(src) is int and src >= 0) or (url and url.scheme in ("http", "https", "rtsp") and url.netloc)):
        raise HTTPException(400, "source must be a device index or an http, https or rtsp URL")
    slot = want_slot(body.get("slot"))
    with SRC_LOCK:
        need("live")
        if any(c.source == src and SLOTS.get(c.id) != slot for c in P.cams.values()) or \
                any(c.source == src for c in P.cams.values()) and not slot:
            raise HTTPException(409, "already running")
        if slot:                                  # v1.21 (D82): a source started in a slot replaces the one there
            stop(in_slot(slot))
        else:                                     # no slot asked: the first free column, if any
            slot = next((k for k in range(1, N_SLOTS + 1) if not in_slot(k)), None)
        cfg = next((c for c in CFG["cameras"] if c["source"] == src), {})   # keeps its door/watch zone (E-16)
        out = start({"name": body.get("name") or cfg.get("name") or str(src), "source": src,
                     "door_zone": cfg.get("door_zone"), "watch_zone": cfg.get("watch_zone")}, loop=True)
        if slot:
            SLOTS[out["id"]] = slot
        return out | {"slot": slot}


@app.get("/api/cameras")
def cameras():
    out = []
    for cid, c in list(P.cams.items()):
        label, onset = LABELS.get(Path(str(c.source)).name, (None, None)) if c.kind == "file" else (None, None)
        out.append({"id": cid, "name": c.name, "source_type": c.kind, "source": c.source, "status": c.status,
                    "fps": round(c.fps(), 1), "has_door_zone": bool(c.door_zone), "loop": c.loop,
                    "t_first": c.t_first, "label": label, "onset_s": onset,   # P3b: clip result card
                    "slot": SLOTS.get(cid)})                                   # v1.21 (D82): dashboard column
    return out


@app.post("/api/cameras/upload")
async def upload(request: Request, name: str, slot: int = None):
    """FR-5 (v1.9): raw file body, ?name=; bare file name, a video extension in UPLOAD_EXT, ≤ 500 MB, written as it arrives.
    P3b: Clips mode only; it replaces the clip that is playing (v1.21: the one in ?slot=, if given)."""
    need("clips")
    slot = want_slot(slot)
    name = Path(name).name
    if not name or Path(name).suffix.lower() not in UPLOAD_EXT:
        raise HTTPException(400, "file must be a video: " + ", ".join(sorted(UPLOAD_EXT)))
    if int(request.headers.get("content-length") or 0) > UPLOAD_MAX:
        raise HTTPException(413, "file is over 500 MB")
    path, n = DATA / "uploads" / str(time.time_ns()) / name, 0     # bare name kept: labels.csv matches it (onset)
    path.parent.mkdir(parents=True)
    with open(path, "wb") as f:
        async for chunk in request.stream():
            n += len(chunk)
            if n > UPLOAD_MAX:
                f.close(); path.unlink()
                raise HTTPException(413, "file is over 500 MB")
            f.write(chunk)
    if not n:
        path.unlink()
        raise HTTPException(400, "empty file")
    return await asyncio.to_thread(play_clip, str(path), name, slot)


@app.delete("/api/cameras/{cid}")
def remove(cid: str):
    """The tile's ■ button: stops the source and releases the device."""
    with SRC_LOCK:
        cam = P.cams.get(cid)
        if not cam:
            raise HTTPException(404)
        P.remove_camera(cid)
        SLOTS.pop(cid, None)
        cam.join(1.5)
    notify("camera_status", {"camera_id": cid, "status": "down"})
    return {"id": cid, "removed": True}


@app.get("/snapshot/{cid}")
def snapshot(cid: str):
    """The detector's newest annotated JPEG (boxes, ids, zones). The tile polls it at ~10 fps and swaps a frame in
    only once it has fully loaded (D72): Safari painted half-received MJPEG frames as grey."""
    det = P.dets.get(cid)
    if det is None or det.jpeg is None:
        raise HTTPException(404)
    return Response(det.jpeg, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@app.get("/media/mosaics/{cid}.jpg")
def mosaic(cid: str):
    if cid not in MOSAICS:
        raise HTTPException(404)
    return Response(MOSAICS[cid], media_type="image/jpeg", headers={"Cache-Control": "no-store"})


def where(**f):
    cl, args = [], []
    for col, op, v in (("camera_id", "=", f.get("camera")), ("category", "=", f.get("category")),
                       (f["tcol"], ">=", f.get("frm")), (f["tcol"], "<=", f.get("to")), ("status", "=", f.get("status"))):
        if v is not None:
            cl.append(f"{col} {op} ?"); args.append(v)
    return (" WHERE " + " AND ".join(cl) if cl else ""), args


@app.get("/api/events")
def events(camera: str = None, category: str = None, status: str = None, frm: float = Query(None, alias="from"),
           to: float = None, limit: int = 50, q: str = None):   # q: keyword search (FTS5, D53)
    w, args = where(camera=camera, category=category, status=status, frm=frm, to=to, tcol="start_ts")
    if q and (words := re.findall(r"[a-z0-9]+", q.lower())):
        w += (" AND " if w else " WHERE ") + "id IN (SELECT rowid FROM events_fts WHERE events_fts MATCH ?)"
        args.append(chatbot.fts_query(words))
    return P.db.rows(f"SELECT * FROM events{w} ORDER BY start_ts DESC LIMIT ?", args + [min(limit, 500)])


@app.get("/api/events/{eid}")
def event(eid: int):
    rows = P.db.rows("SELECT * FROM events WHERE id=?", (eid,))
    if not rows:
        raise HTTPException(404)
    return rows[0] | {"observations": P.db.rows("SELECT * FROM observations WHERE event_id=? ORDER BY ts", (eid,))}


@app.post("/api/events/{eid}/ack")
def ack(eid: int):
    P.db.update("events", eid, {"status": "acknowledged"})
    for ev in list(P.events.open.values()):
        if ev["id"] == eid:
            ev["status"] = "acknowledged"
    out = event(eid)
    send("event_update", {k: v for k, v in out.items() if k != "observations"})
    return out


@app.post("/api/events/{eid}/dismiss")
def dismiss(eid: int):
    """FR-25: operator marks a false alarm. Kept for audit (status dismissed, reason operator), hidden from the feed and
    the chat, counted per camera-hour in the report, exported as labelled examples (/api/report/feedback.csv)."""
    event(eid)                                           # 404 if unknown
    P.db.update("events", eid, {"status": "dismissed", "dismiss_reason": "operator"})
    P.events.dismiss(eid)
    save_feedback(eid)
    out = event(eid)
    send("event_update", {k: v for k, v in out.items() if k != "observations"})
    return out


def camera_hours():
    """Monitored time: first → last real observation per camera (seeded history excluded), summed."""
    r = P.db.rows("SELECT SUM(t) h FROM (SELECT MAX(ts) - MIN(ts) t FROM observations WHERE seeded=0 GROUP BY camera_id)")
    return (r[0]["h"] or 0) / 3600


@app.get("/api/report")
def report():
    """FR-20 report tab: the newest dev-set pass (bench/results/ab_dev_*), plus live operator numbers from the DB."""
    dev = sorted((ROOT / "bench" / "results").glob("ab_dev_*_summary.json"), key=lambda p: p.stat().st_mtime)
    from bench import metrics as bm                           # pure, unit-tested in tests/test_report.py
    acc = bm.dev_report(dev[-1], {c: on for c, (_, on) in LABELS.items()}, CFG["vlm"]["mosaic_span_s"]) if dev else None
    ev = P.db.rows("SELECT category, status, dismiss_reason, COUNT(*) n FROM events WHERE seeded=0 GROUP BY 1, 2, 3")
    fa = sum(r["n"] for r in ev if r["dismiss_reason"] == "operator")
    hours = camera_hours()
    m = metrics()
    return {"accuracy": acc, "latency": m["latency"] | {"trigger_to_alert_p95_ms": m["vlm"].get("alert_p95_ms")},
            "operator": {"events": sum(r["n"] for r in ev), "false_alarms": fa, "camera_hours": round(hours, 3),
                         "false_alarms_per_camera_hour": round(fa / hours, 2) if hours >= 0.05 else None,
                         "by_category": ev}}


FEEDBACK = DATA / "feedback" / "operator_false_alarms.csv"
FB_COLS = ["event_id", "camera_id", "category", "peak_confidence", "ts", "obs_category", "confidence", "probs", "trigger",
           "summary", "label"]


def save_feedback(eid):
    """Append the dismissed event's observations to FEEDBACK (FR-25 labels). A file, not the DB: the live tables are
    cleared on every pipeline start (E-14), the operator's labels must outlive that."""
    rows = P.db.rows("SELECT e.id event_id, e.camera_id, e.category, e.peak_confidence, o.ts, o.category obs_category, "
                     "o.confidence, o.probs, o.trigger, o.summary FROM events e JOIN observations o ON o.event_id = e.id "
                     "WHERE e.id=? ORDER BY o.ts", (eid,))
    FEEDBACK.parent.mkdir(parents=True, exist_ok=True)
    new = not FEEDBACK.exists()
    with FEEDBACK.open("a", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, FB_COLS)
        if new:
            w.writeheader()
        w.writerows({**r, "probs": json.dumps(r["probs"]), "label": "false_alarm"} for r in rows)


@app.get("/api/report/feedback.csv")
def feedback_csv():
    """Every operator-marked false alarm so far, one row per observation with its probabilities, for threshold
    calibration on the dev set (P8)."""
    body = FEEDBACK.read_text(encoding="utf-8") if FEEDBACK.exists() else ",".join(FB_COLS) + "\n"
    return Response(body, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=operator_false_alarms.csv"})


@app.get("/api/observations")
def observations(camera: str = None, frm: float = Query(None, alias="from"), to: float = None, limit: int = 50):
    w, args = where(camera=camera, frm=frm, to=to, tcol="ts")
    return P.db.rows(f"SELECT * FROM observations{w} ORDER BY ts DESC LIMIT ?", args + [min(limit, 500)])


@app.post("/api/chat")
def chat(body: dict):
    """§7.5 / §5a.2. Sync handler: runs in the threadpool, so a summary waiting on the model never blocks the loop."""
    q = str(body.get("question") or "").strip()
    if not q or len(q) > 500:
        raise HTTPException(400, "question: 1-500 characters")
    return chatbot.answer(q, P.db, P.arb, dict(P.events.cam_names), session=str(body.get("session_id") or "")[:64] or None)


@app.get("/api/digest")
def digest(hours: float = 8, camera: str = None):
    """FR-17 shift-handover report for the last `hours` (≤ 24), all cameras or one. Sync: waits on the model in the threadpool."""
    if not 0 < hours <= 24:
        raise HTTPException(400, "hours: more than 0, at most 24")
    return chatbot.digest(P.db, P.arb, dict(P.events.cam_names), hours=hours, camera=camera)


@app.get("/api/metrics")
def get_metrics():
    return metrics()


@app.get("/api/arbiter")
def arbiter_stats(window: float = 60.0):
    """Model-slot instrumentation (D87): queue wait / run time by priority, cancellations, stale drops, per-camera
    starvation, GPU duty per 10 s, and the person_down second-look log."""
    return P.arb.stats(window=window) | {"held_log": [list(x) for x in P.events.held_log][-50:],
                                         "relooks": [list(x) for x in getattr(P, "relooks", [])][-50:]}


@app.post("/api/ui/latency")
async def ui_latency(request: Request):
    """v1.9: the browser's measured store→card ms. It compares the browser clock with this server's, so only a
    browser on this machine is valid; readings from other devices are ignored."""
    if request.client.host not in ("127.0.0.1", "::1", "localhost"):
        return {"accepted": False, "reason": "not the server machine"}
    v = (await request.json()).get("ms")
    if not isinstance(v, (int, float)) or not 0 <= v < 60000:
        raise HTTPException(400)
    S2C.append(round(v, 1))
    return {"accepted": True}


NOTIFY: Notifier = None                          # D89: opt-in phone notifications, off by default


@app.get("/api/notify")
def notify_status():
    """D89: whether phone notifications are on, which channels are configured, the last deliveries."""
    if NOTIFY is None:
        raise HTTPException(503, "notifier not running")
    return NOTIFY.status()


@app.post("/api/notify")
def notify_set(body: dict):
    """D89: switch phone notifications on or off at runtime (the demo turns them on only after the offline run)."""
    if NOTIFY is None:
        raise HTTPException(503, "notifier not running")
    if not isinstance(body.get("enabled"), bool):
        raise HTTPException(400, "body must be {\"enabled\": true|false}")
    if body["enabled"] and not NOTIFY.channels():
        raise HTTPException(409, "no channel: start with HONEYVIEW_PAGER=1 (local phones), or set HACKHIVE_NTFY_URL / the Telegram pair")
    NOTIFY.enabled = body["enabled"]
    return NOTIFY.status()


@app.post("/api/notify/test")
def notify_test():
    """D89: one test message to every configured channel, through the same worker (returns at once). Works while
    notifications are off, on purpose: it checks a phone is listening before they are switched on."""
    if NOTIFY is None or not NOTIFY.channels():
        raise HTTPException(409, "no channel configured")
    NOTIFY.test()                                 # drop-oldest when full: never a 500
    return {"queued": True}


app.mount("/media/keyframes", StaticFiles(directory=DATA / "keyframes", check_dir=False), name="keyframes")
app.mount("/media/thumbs", StaticFiles(directory=DATA / "thumbs", check_dir=False), name="thumbs")
if DIST.exists():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="web")


def serve(port=8000):
    import uvicorn
    global P, NOTIFY
    P = Pipeline([], emit=emit)                  # P3b: nothing runs at boot; config.yaml cameras are Live presets
    P.start()
    pager = None
    if (CFG.get("pager") or {}).get("enabled") or os.environ.get("HONEYVIEW_PAGER") == "1":
        pager = Pager().start()                   # D89: read-only, token-protected, LAN only; the dashboard stays on 127.0.0.1
        print("HoneyView Pager (open on phones on the same Wi-Fi / hotspot):\n  " + "\n  ".join(pager.urls()), flush=True)
    NOTIFY = Notifier(pager=pager)
    NOTIFY.start()
    try:
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")   # no auth: never on venue Wi-Fi
    finally:
        P.events.close_all(); P.stop()


def selfcheck():
    """Real pipeline (sample clip) on a spare port; checks every P3 endpoint, MJPEG, SSE latency and upload rules,
    plus P3b: empty boot, playlist, one clip at a time, mode switch (history kept), live URL rules, ■ stop."""
    import httpx
    import uvicorn
    global P
    port, clip = 8765, "data/demo/sample_bus.mp4"
    P = Pipeline([], emit=emit)
    P.start()
    srv = uvicorn.Server(uvicorn.Config(app, port=port, log_level="warning"))
    threading.Thread(target=srv.run, daemon=True).start()
    while not srv.started:
        time.sleep(0.05)
    u = f"http://127.0.0.1:{port}"
    with httpx.Client(base_url=u, timeout=30) as c:
        assert c.get("/api/cameras").json() == [] and c.get("/api/metrics").json()["mode"] == "clips"   # nothing at boot
        pl = c.get("/api/clips").json()
        assert any(x["path"] == clip and x["label"] == "normal" for x in pl), pl
        assert c.post("/api/clips/play", json={"path": "/etc/passwd"}).status_code == 400
        assert c.post("/api/cameras", json={"source": 0}).status_code == 409          # live sources: Live mode only
        assert c.post("/api/clips/play", json={"path": clip}).json()["id"] == "cam1"
        time.sleep(1)
        cams = c.get("/api/cameras").json()
        assert len(cams) == 1 and cams[0]["status"] == "live" and not cams[0]["loop"], cams
        r = c.get("/snapshot/cam1")                  # one whole annotated JPEG (D72)
        assert r.headers["content-type"] == "image/jpeg" and r.content[:2] == b"\xff\xd8" and r.content[-2:] == b"\xff\xd9"
        assert c.get("/snapshot/nope").status_code == 404
        # SSE: metrics arrive; an alert pushed through emit() reaches the client within the budget
        got, t_rx = {}, {}

        def listen():
            with httpx.stream("GET", u + "/sse", timeout=None) as r:
                kind = None
                for line in r.iter_lines():
                    if line.startswith("event:"):
                        kind = line[6:].strip()
                    elif line.startswith("data:"):
                        got.setdefault(kind, json.loads(line[5:])); t_rx.setdefault(kind, time.time())
                        if {"metrics", "observation", "trace", "alert"} <= set(got):
                            return
        th = threading.Thread(target=listen, daemon=True); th.start()
        time.sleep(1)
        fake = {"id": -1, "camera_id": "cam1", "category": "fighting", "severity": "high", "peak_confidence": 0.9,
                "time_to_alert_ms": 900, "_t_alert": time.time(), "_probs": [("fighting", .9), ("normal", .08),
                                                                              ("suspicious_activity", .02)]}
        emit("alert", fake)                        # transport test only; not stored, id -1
        th.join(25)
        assert {"metrics", "observation", "trace", "alert"} <= set(got), list(got)
        sse_ms = (t_rx["alert"] - got["alert"]["t_stored"]) * 1000
        assert sse_ms < 50, sse_ms
        m = got["metrics"]
        assert m["cameras"]["cam1"]["now"] and "gpu_duty_pct" in m["vlm"] and "latency" in m, m
        tr = got["trace"]
        assert tr["stages"] and c.get(tr["mosaic_url"]).content[:2] == b"\xff\xd8", tr
        assert c.post("/api/ui/latency", json={"event_id": -1, "ms": 12.5}).json()["accepted"]
        assert c.get("/api/metrics").json()["latency"]["store_to_card_ms"]["last"] == 12.5
        assert c.get("/api/events").status_code == 200 and isinstance(c.get("/api/observations").json(), list)
        r = c.post("/api/chat", json={"session_id": "s", "question": "How many incidents today?"}).json()
        assert r["how"]["mode"] in ("template", "model") and r["answer"] and "filters" in r, r   # P4; D75: model answers
        assert c.post("/api/chat", json={"question": ""}).status_code == 400 and c.get("/api/events?q=zzqx").json() == []
        assert all(o["thumb_path"] is None for o in c.get("/api/observations").json() if o["category"] == "normal")
        # FR-25 mark false alarm + FR-20 report (a throwaway event, deleted after so the real counts stay true)
        eid = P.db.insert("events", {"camera_id": "selfcheck", "category": "fighting", "severity": "critical",
                                     "start_ts": time.time(), "status": "open"})
        try:
            d = c.post(f"/api/events/{eid}/dismiss").json()
            assert d["status"] == "dismissed" and d["dismiss_reason"] == "operator", d
            assert c.post("/api/events/999999999/dismiss").status_code == 404
            rep = c.get("/api/report").json()
            assert rep["operator"]["false_alarms"] >= 1 and "onset_to_alert_ms" in rep["latency"], rep
            assert c.get("/api/report/feedback.csv").text.startswith("event_id,camera_id")
            dg = c.get("/api/digest?hours=24").json()
            assert dg["headline"].startswith("Shift handover") and dg["narrative"] and "how" in dg, dg
            assert c.get("/api/digest?hours=0").status_code == 400
        finally:
            with P.db.lock:
                P.db.con.execute("DELETE FROM events WHERE id=?", (eid,))
        # upload rules (v1.9 conditions): bad extension 400, path stripped, real clip -> new camera, removable
        assert c.post("/api/cameras/upload?name=x.exe", content=b"1").status_code == 400
        r = c.post("/api/cameras/upload?name=../../evil/clip.mp4", content=Path(clip).read_bytes())
        assert r.status_code == 200 and r.json()["name"] == "clip.mp4", r.text
        new = r.json()["id"]
        assert any((DATA / "uploads").glob("*/clip.mp4"))
        assert [x["id"] for x in c.get("/api/cameras").json()] == [new]               # the upload replaced cam1
        assert c.delete(f"/api/cameras/{new}").status_code == 200
        assert new not in [x["id"] for x in c.get("/api/cameras").json()]
        # v1.21 (D82) slots: clips side by side, one per column; a slot replaces only its own clip; no slot = one at a time
        other = next(x["path"] for x in c.get("/api/clips").json() if x["path"] != clip)
        a = c.post("/api/clips/play", json={"path": clip, "slot": 1}).json()
        b = c.post("/api/clips/play", json={"path": other, "slot": 2}).json()
        assert (a["slot"], b["slot"]) == (1, 2) and {x["slot"] for x in c.get("/api/cameras").json()} == {1, 2}, (a, b)
        a2 = c.post("/api/clips/play", json={"path": other, "slot": 1}).json()
        now = {x["id"]: x["slot"] for x in c.get("/api/cameras").json()}
        assert now == {a2["id"]: 1, b["id"]: 2}, now
        for bad in (0, 4, "1", True):
            assert c.post("/api/clips/play", json={"path": clip, "slot": bad}).status_code == 400, bad
        assert c.post("/api/cameras/upload?name=a.mp4&slot=9", content=b"1").status_code == 400
        solo = c.post("/api/clips/play", json={"path": clip}).json()
        assert [(x["id"], x["slot"]) for x in c.get("/api/cameras").json()] == [(solo["id"], 1)]
        # P3b modes: switching stops every source, history stays; Live accepts device indices and stream URLs only
        c.post("/api/clips/play", json={"path": clip})
        n_obs = len(c.get("/api/observations?limit=500").json())
        sw = c.post("/api/mode", json={"mode": "live"}).json()
        assert sw["mode"] == "live" and c.get("/api/cameras").json() == [], sw
        assert c.post("/api/clips/play", json={"path": clip}).status_code == 409
        assert c.post("/api/cameras/upload?name=a.mp4", content=b"1").status_code == 409
        for bad in ("file:///etc/passwd", "/etc/passwd", "data/demo/sample_bus.mp4", "ftp://x/y", "http://", -1, True):
            assert c.post("/api/cameras", json={"source": bad}).status_code == 400, bad
        assert isinstance(c.get("/api/devices").json(), list)
        dead = "rtsp://127.0.0.1:9/none"                                                # no server: stays connecting
        r = c.post("/api/cameras", json={"source": dead, "name": "dead"})
        assert r.status_code == 200 and c.post("/api/cameras", json={"source": dead}).status_code == 409, r.text
        assert r.json()["slot"] == 1 and c.post("/api/cameras", json={"source": dead, "slot": 2}).status_code == 409
        r2 = c.post("/api/cameras", json={"source": "rtsp://127.0.0.1:9/two", "slot": 1})       # replaces slot 1
        assert [(x["source"], x["slot"]) for x in c.get("/api/cameras").json()] == [("rtsp://127.0.0.1:9/two", 1)], r2.text
        r = r2
        assert c.get("/api/cameras").json()[0]["status"] in ("connecting", "reconnecting")
        t = time.time()
        assert c.delete(f"/api/cameras/{r.json()['id']}").status_code == 200 and c.get("/api/cameras").json() == []
        stop_ms = ms(t, time.time())
        c.post("/api/cameras", json={"source": dead})
        back = c.post("/api/mode", json={"mode": "clips"}).json()
        assert back["mode"] == "clips" and c.get("/api/cameras").json() == []
        assert len(c.get("/api/observations?limit=500").json()) >= n_obs                # history never cleared
        if DIST.exists():
            assert b'<div id="root">' in c.get("/").content
    srv.should_exit = True
    P.stop()
    for f in (DATA / "uploads").glob("*/clip.mp4"):
        f.unlink(); f.parent.rmdir()
    print(f"server self-check ok: emit→SSE {sse_ms:.1f} ms, trace stages {[s['name'] for s in tr['stages']]}, "
          f"mode switch {sw['switch_ms']} / {back['switch_ms']} ms, ■ stop {stop_ms} ms, "
          f"web bundle {'served' if DIST.exists() else 'NOT BUILT'}")


if __name__ == "__main__":
    if "--selfcheck" in sys.argv:
        selfcheck()
    else:
        serve()
