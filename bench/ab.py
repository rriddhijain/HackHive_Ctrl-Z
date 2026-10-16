"""P2b A/B tests on the dev clips (PLAN P2b, SPEC §12). One flag per test; results -> bench/results/ab_<test>.csv.

  uv run python -m bench.ab --model    qwen3.5 4B vs 2B, real pipeline + real prompt, one clip at a time, played once
  uv run python -m bench.ab --gate     plain yolo26n vs yolo26n-pose for the gates (FR-6a): detector replayed offline
                                       on every clip at 10 FPS in clip time; per clip: which rules fired, when, and the
                                       track values behind the ones that didn't (fight pair speed, overlap, persons seen)
  uv run python -m bench.ab --gate --check   gate regression check (D72), CPU only, ~2 min; exit 1 on failure.
                                       Every gate or threshold change must pass it (CLAUDE.md)
  uv run python -m bench.ab --dev --tag T  every dev clip alone, played once (the headline accuracy/latency pass)
  uv run python -m bench.ab --test --tag T every test clip (bench/labels.csv split=test, in data/demo/) alone, played once.
                                       --dev and --test also record every model call (probabilities, detector evidence,
                                       mosaic) to data/ab/T/rec/, which --replay / --sweep re-score without the GPU (D86)
  uv run python -m bench.ab --tiles    2x2 mosaic vs person-crop tile 4 (FR-9c) vs the 4 frames as separate images
  uv run python -m bench.ab --run a.mp4 [b.mp4 ...] [--seconds N] [--tag T]   one pipeline run (several clips = several
                                       cameras at once; --seconds loops them): per-camera rows -> ab_run_<tag>.csv
Rows: one per clip: clip, true label, predicted label, confidence, top-3, onset-to-alert ms (needs onset_s; else
start->alert = an upper bound), trigger->alert, gates fired, vetoes (p >= 0.3), key-frame path, calls, queue ms.
The printed summary groups errors by confusion pair with their key-frame paths.
"""
import argparse
import base64
import csv
import itertools
import json
import shutil
import statistics
import threading
import time
from collections import defaultdict, deque
from pathlib import Path

import cv2
from ultralytics import YOLO

from app import vlm
from app.config import CFG, ROOT
from app.gate import _old_enough, gate, norm_speed, overlap

V = CFG["vlm"]

DET, G = CFG["detector"], CFG["gate"]
DEV = ROOT / "data" / "dev"
OUT = ROOT / "bench" / "results"


def clips(split="dev"):
    """dev: every clip in data/dev/<category>/ (label from bench/labels.csv, else its folder); test: the labels.csv rows
    with split=test, played from data/demo/."""
    from app.pipeline import load_labels
    if split == "test":
        return [(ROOT / "data" / "demo" / r["clip"], r["label"]) for r in csv.DictReader(open(ROOT / "bench" / "labels.csv"))
                if r["split"] == "test"]
    labels = load_labels()
    return [(p, labels.get(p.name, (p.parent.name, None))[0]) for p in sorted(DEV.glob("*/*")) if p.suffix in (".mp4", ".avi")]


def replay_gates(path, model_path, cfg=G):
    """Detector + gates on a clip at DET fps in clip time (same resize/track args as app.detect). Returns a dict."""
    m = YOLO(str(ROOT / model_path))
    pose = "pose" in str(model_path)
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    step = max(1, round(fps / DET["fps"]))
    hists, last_seen, fired, yolo_ms = {}, {}, defaultdict(list), []
    d = {"max_persons": 0, "frames_2p": 0, "frames_overlap": 0, "max_overlap_speed": 0.0, "max_speed": 0.0}
    i = 0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        if i % step:
            i += 1
            continue
        t = i / fps
        i += 1
        h, w = f.shape[:2]
        small = cv2.resize(f, (DET["frame_width"], int(h * DET["frame_width"] / w)))
        t0 = time.perf_counter()
        r = m.track(small, persist=True, tracker="bytetrack.yaml", classes=[0] if pose else DET["classes"],
                    conf=DET["conf"], imgsz=DET["imgsz"], device=DET["device"], verbose=False)[0]
        yolo_ms.append((time.perf_counter() - t0) * 1000)
        if r.boxes is not None and r.boxes.id is not None:
            for box, tid, cls in zip(r.boxes.xyxy.tolist(), r.boxes.id.int().tolist(), r.boxes.cls.int().tolist()):
                if cls == 0:
                    hists.setdefault(tid, deque(maxlen=60)).append((t, *box)); last_seen[tid] = t
        for tid in [k for k, v in last_seen.items() if t - v > 5]:
            del hists[tid], last_seen[tid]
        live = {k: list(v) for k, v in hists.items() if last_seen[k] == t}
        d["max_persons"] = max(d["max_persons"], len(live))
        d["frames_2p"] += len(live) >= 2
        old = {k: v for k, v in live.items() if _old_enough(v, cfg)}
        for k, v in old.items():
            d["max_speed"] = max(d["max_speed"], norm_speed(v))
        ov = [(a, b) for a, b in itertools.combinations(sorted(old), 2) if overlap(old[a][-1], old[b][-1])]
        d["frames_overlap"] += bool(ov)
        for a, b in ov:
            d["max_overlap_speed"] = max(d["max_overlap_speed"], norm_speed(old[a]), norm_speed(old[b]))
        for tr in gate("ab", {k: list(v) for k, v in hists.items()}, cfg):
            fired[tr["rule"] + (":" + tr["kind"] if tr.get("kind") else "")].append(round(t, 1))
    yolo_ms = sorted(yolo_ms[3:])
    return {**{k: round(v, 2) if isinstance(v, float) else v for k, v in d.items()},
            "fired": {k: v for k, v in fired.items()}, "first_fire_s": min((v[0] for v in fired.values()), default=None),
            "yolo_ms_p50": round(yolo_ms[len(yolo_ms) // 2], 1) if yolo_ms else None, "duration_s": round(i / fps, 1)}


def test_gate():
    rows = []
    for path, label in clips():
        for name, mp in (("plain", DET["model"]), ("pose", CFG["detector_pose_ab"]["model"])):
            r = replay_gates(path, mp)
            rows.append({"clip": path.name, "label": label, "detector": name, **r})
            print(rows[-1], flush=True)
    write("gate", rows)
    return rows


KNOWN_MISS = {"v026.avi": "D64: nano never detects both fighters, so no gate can fire; only a baseline can catch it"}
MAX_FALSE_PER_MIN = 2.0   # gate ①s per camera-minute, normal + look-alike clips pooled


def check_gates():
    """--gate --check (D72): the real Detector + Scheduler on every clip in data/dev/ at 10 FPS in clip time, CPU only,
    every model call answered at once: incident clips as their label, the rest confident normal, so the D61/D64
    silences act as they do live. Passes when every incident clip's category gate fires from onset − 1 s to onset + 5 s
    (any time without an onset; so a later look-alike in the clip can't pass for it), as a new ① or merged into one
    (D72), except KNOWN_MISS, and the normal/look-alike clips together make ≤ MAX_FALSE_PER_MIN ①s per camera-minute."""
    from types import SimpleNamespace as NS
    from app.detect import Detector
    from app.pipeline import load_labels
    from app.scheduler import Scheduler
    from app.vlm import GATE_CAT

    class Instant:                                      # the arbiter, every call answered at once
        cv, running = threading.RLock(), None
        def __init__(self, on_call): self.on_call = on_call
        def waiting(self, prio=None, cam=None): return []
        def duty(self): return 0.0
        def submit(self, r): self.on_call(r); return r

    onsets = {k: v[1] for k, v in load_labels().items()}
    fails, n_false, minutes = [], 0, 0.0
    for path, label in clips():
        det, fired = Detector(NS(id="chk", door_zone=None, watch_zone=None)), []

        def on_call(r):
            newest = det.buffer[-1]
            if r["prio"] == 3:
                return sched.note_call("chk", newest)
            fired.append((round(newest[0], 1), r["rule"] + (":" + r["kind"] if r.get("kind") else "")))
            if label == "normal":                       # confident-normal verdict
                if r.get("kind") == "horizontal":
                    sched.silence("chk", r["track_ids"], newest[0])
                if r["rule"] == "fighting":
                    sched.silence_pair("chk", r["track_ids"], det.person_hists(), newest[0])
        sched = Scheduler(Instant(on_call), NS(is_open=lambda cam, cat: False, has_open=lambda cam: False))
        fires, trigger = [], sched.trigger                 # every gate fire, whether it makes a ① or merges into one
        sched.trigger = lambda d, tr, now: fires.append((round(now, 1), tr["rule"])) or trigger(d, tr, now)
        cap = cv2.VideoCapture(str(path))
        fps, i = cap.get(cv2.CAP_PROP_FPS) or 30, 0
        step = max(1, round(fps / DET["fps"]))
        while (got := cap.read())[0]:
            if i % step == 0:
                det._process(got[1], i / fps, i)
                sched.on_frame(det)
            i += 1
        dur, on = i / fps, onsets.get(path.name)
        if label == "normal":
            n_false += len(fired); minutes += dur / 60
            verdict = f"{len(fired) / (dur / 60):.1f} ①/min"
        elif label not in GATE_CAT.values():
            verdict = "no gate for this category"
        elif any(GATE_CAT.get(r) == label and (on is None or on - 1 <= t <= on + 5) for t, r in fires):
            verdict = "fires"
        elif path.name in KNOWN_MISS:
            verdict = "KNOWN MISS: " + KNOWN_MISS[path.name]
        else:
            verdict = "MISSED"; fails.append(path.name)
        starts, last = {}, {}                           # gate fire episodes (> 1 s apart), per rule
        for t, r in fires:
            if t - last.get(r, -9) > 1.0:
                starts.setdefault(r, []).append(t)
            last[r] = t
        print(f"{path.name:<22} {label:<9} {dur:5.1f} s  onset {on}  {verdict:<12} fires {starts}  ①s {fired[:8]}", flush=True)
    rate = n_false / minutes if minutes else 0.0
    print(f"normal + look-alike clips: {n_false} gate ①s in {minutes:.1f} camera-min = {rate:.2f}/min "
          f"(limit {MAX_FALSE_PER_MIN})")
    if rate > MAX_FALSE_PER_MIN:
        fails.append(f"false-trigger rate {rate:.2f}/min")
    print("gate check", "FAILED: " + ", ".join(fails) if fails else "ok")
    if fails:
        raise SystemExit(1)


def pct(xs, q):
    xs = sorted(x for x in xs if x is not None)
    return xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))] if xs else None


def run(paths, seconds=None, tag="run"):
    """Real Pipeline (app.pipeline), one camera per clip, in this process. Played once unless seconds (looped).
    Returns (per-camera rows, run totals)."""
    from app.pipeline import Pipeline, load_labels
    labels = load_labels()
    cams = [{"id": f"cam{i + 1}", "name": Path(c).name, "source": str(c)} for i, c in enumerate(paths)]
    traces = []
    p = Pipeline(cams, loop=bool(seconds), emit=lambda k, d: traces.append(d) if k == "trace" else None)
    subs, submit = [], p.arb.submit
    p.arb.submit = lambda r: (subs.append((r["cam"], r["trigger"], time.time())), submit(r))[1]
    # Recording (D86): the cross-check's input and the event rules' input of every call, so --replay can re-run
    # vlm.cross_check + EventManager.decide with other thresholds without the GPU. One arbiter worker = calls are serial.
    rec, cross, decide = [], vlm.cross_check, p.events.decide
    def cross_rec(pr, ev, *a, **k):
        rec.append({"p": {c: round(v, 5) for c, v in pr.items()}, "ev": {**ev, "triggers": sorted(ev["triggers"])}})
        return cross(pr, ev, *a, **k)
    def decide_rec(cam, c, sub, trig, ts, t_ref, t_alert=None):
        t_alert = t_alert or time.time()
        rec[-1].update(cam=cam, sub=sub, ts=ts, t_ref=t_ref, t_alert=t_alert, c_top=max(c, key=c.get))
        return decide(cam, c, sub, trig, ts, t_ref, t_alert)
    vlm.cross_check, p.events.decide = cross_rec, decide_rec
    try:
        p.start()
        if seconds:
            time.sleep(seconds)
        else:
            while any(c.status not in ("ended", "down", "stopped") for c in p.cams.values()):
                time.sleep(0.2)
            while p.arb.waiting() or p.arb.running:
                time.sleep(0.2)
    finally:
        vlm.cross_check = cross
    t_end = time.time()
    p.stop()
    wall = t_end - p.t0
    rows = []
    for cid, c in p.cams.items():
        label, onset = labels.get(Path(str(c.source)).name, (None, None))
        evs = p.db.rows("SELECT * FROM events WHERE camera_id=? ORDER BY peak_confidence DESC", (cid,))
        obs = p.db.rows("SELECT * FROM observations WHERE camera_id=? ORDER BY ts", (cid,))
        best = evs[0] if evs else None
        pred = best["category"] if best else "normal"
        o = max((x for x in obs if x["probs"]), key=lambda x: x["probs"].get(pred, 0), default=None) or (obs[-1] if obs else None)
        probs = (o["probs"] or {}) if o else {}
        hit = next((t for cam, cat, t, _ in p.alerts if cam == cid and cat == pred and pred != "normal"), None)
        calls = [x for x in p.calls if x["cam"] == cid]
        busy = sum(x["call_ms"] or 0 for x in calls if x.get("call_ms")) / 1000
        gates = [(tr[5:], round(t - c.t_first, 1)) for cam, tr, t in subs if cam == cid and tr.startswith("gate:") and c.t_first]
        kf = best["keyframe_paths"][-1] if best and best["keyframe_paths"] else (o["thumb_path"] if o else None)
        if kf:   # event ids restart at 1 every run: keep a per-run copy (data/, gitignored)
            dst = ROOT / "data" / "ab" / tag / Path(str(c.source)).with_suffix(".jpg").name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(ROOT / kf, dst)
            kf = str(dst.relative_to(ROOT))
        # onset -> the first gate of the label's category (onset - 1 s on): how much of onset -> alert is the trigger
        g_on = next((t for r, t in gates if vlm.GATE_CAT.get(r) == label and onset is not None and t >= onset - 1), None)
        rows.append({"clip": Path(str(c.source)).name, "label": label, "pred": pred, "onset_s": onset,
                     "confidence": round(best["peak_confidence"] if best else probs.get("normal", 0), 3),
                     "top3": " ".join(f"{k}:{v:.2f}" for k, v in sorted(probs.items(), key=lambda kv: -kv[1])[:3]),
                     "onset_to_alert_ms": round((hit - c.t_first - onset) * 1000) if hit and onset is not None else None,
                     "onset_to_gate_ms": round((g_on - onset) * 1000) if g_on is not None else None,
                     "start_to_alert_ms": round((hit - c.t_first) * 1000) if hit and c.t_first else None,
                     "trigger_to_alert_ms": best["time_to_alert_ms"] if best else None,
                     "trigger_to_alert_p95": pct([e["time_to_alert_ms"] for cam, _, _, e in p.alerts if cam == cid], .95),
                     "alerts": sum(cam == cid for cam, *_ in p.alerts),
                     "gate_fired": " ".join(f"{r}@{t}s" for r, t in gates[:6]) or None,
                     "vetoes": " ".join(f"{v['category']}:{v['p_before']}" for v in p.vetoes
                                        if v["camera_id"] == cid and v["p_before"] >= 0.3) or None,
                     "keyframe": kf,
                     "calls_p1": sum(x["prio"] == 1 for x in calls), "calls_p3": sum(x["prio"] == 3 for x in calls),
                     "baselines_skipped": p.sched.skipped_by.get(cid, 0) if hasattr(p.sched, "skipped_by") else None,
                     "queue_ms_p50": pct([x.get("queue_ms") for x in calls if x["prio"] == 1], .5),
                     "queue_ms_p95_p1": pct([x.get("queue_ms") for x in calls if x["prio"] == 1], .95),
                     "cam_duty": round(busy / wall, 3), "summary": best["summary"] if best else (o["summary"] if o else None)})
    record(tag, p, rec, traces, labels)
    full = [x for x in p.calls if x.get("call_ms") is not None]
    tot = {"wall_s": round(wall, 1), "gpu_duty": round(p.arb.duty(window=wall, now=t_end), 3),
           "model_tta_p50": pct([x["model_tta_ms"] for x in full], .5), "call_ms_p50": pct([x["call_ms"] for x in full], .5),
           "gate_triggers": p.sched.n_triggers, "skipped": p.sched.skipped, "vlm_errors": p.vlm_errors,
           "vetoes_logged": len(p.vetoes), "vetoes_p_ge_0.3": sum(v["p_before"] >= 0.3 for v in p.vetoes),
           "alerts": [(cam, cat, round(e["time_to_alert_ms"])) for cam, cat, _, e in p.alerts]}
    return rows, tot


def record(tag, p, rec, traces, labels):
    """data/ab/<tag>/rec/<clip>.json per camera: every call's cross-check input (p, ev), event-rule input (sub, ts,
    t_ref, t_alert), trigger, hints, raw JSON and its mosaic (data/ab/<tag>/mosaic/<clip>/NNN.jpg)."""
    rdir = ROOT / "data" / "ab" / tag / "rec"
    rdir.mkdir(parents=True, exist_ok=True)
    tr = {(t["camera_id"], t["created"]): t for t in traces}
    for cid, c in p.cams.items():
        name = Path(str(c.source)).name
        cap = cv2.VideoCapture(str(c.source))
        dur = cap.get(cv2.CAP_PROP_FRAME_COUNT) / (cap.get(cv2.CAP_PROP_FPS) or 30)
        calls = []
        for i, r in enumerate(x for x in rec if x.get("cam") == cid):
            if t := tr.get((cid, r["t_ref"])):
                m = rdir.parent / "mosaic" / Path(name).stem / f"{i:03d}.jpg"
                m.parent.mkdir(parents=True, exist_ok=True)
                m.write_bytes(base64.b64decode(t["mosaic_b64"]))
                r = r | {"trigger": t["trigger"], "hints": t["hints"], "raw": t["raw_json"], "mosaic": str(m.relative_to(ROOT))}
            calls.append(r)
        label, onset = labels.get(name, (None, None))
        (rdir / f"{Path(name).stem}.json").write_text(json.dumps(
            {"clip": name, "label": label, "onset_s": onset, "t_first": c.t_first, "duration_s": round(dur, 2), "calls": calls}))


class _NoDB:                                            # EventManager only inserts and updates rows
    n = 0
    def insert(self, table, row): self.n += 1; return self.n
    def update(self, *a): pass


def load_recs(tag):
    """{clip: recording} for data/ab/<tag>/rec/*.json, each with its split from bench/labels.csv."""
    split = {r["clip"]: r["split"] for r in csv.DictReader(open(ROOT / "bench" / "labels.csv"))}
    recs = [json.loads(f.read_text()) for f in sorted((ROOT / "data" / "ab" / tag / "rec").glob("*.json"))]
    return {r["clip"]: r | {"split": split.get(r["clip"], "dev")} for r in recs}


def replay(r, probs=None):
    """A recorded clip through vlm.cross_check + EventManager.decide with the CURRENT config, no GPU (D86).
    probs: optional per-call probabilities replacing the recorded ones (a re-asked prompt variant).
    Same calls at the same times: a setting that would have changed which calls were made (a cooldown, a
    confident-normal silence) is approximated, which is why the chosen setting is confirmed by a real pass."""
    from app.events import EventManager
    E, em, opened = CFG["events"], EventManager(_NoDB()), []
    for i, x in enumerate(c for c in r["calls"] if "cam" in c):
        ev = x["ev"] | {"triggers": set(x["ev"]["triggers"])}
        c, _ = vlm.cross_check(vlm.calibrate((probs or {}).get(i, x["p"]), E["calibration_T"]), ev)
        em.tick(now=x["t_alert"])
        opened += em.decide(x["cam"], c, x["sub"], ev["triggers"], x["ts"], x["t_ref"], x["t_alert"])[0]
    t0, on = r["t_first"], r["onset_s"]
    pre = [e for e in opened if r["label"] == "normal" or (on is not None and e["start_ts"] - t0 < on - 1)]
    # an incident clip is judged on its alerts from onset - 1 s on: a look-alike alert earlier is a false alarm, never a hit
    scored = opened if r["label"] == "normal" else [e for e in opened if e not in pre]
    pred = max(scored, key=lambda e: e["peak_confidence"])["category"] if scored else "normal"
    hit = next((e for e in scored if e["category"] == r["label"]), None)
    return {"clip": r["clip"], "label": r["label"], "pred": pred, "split": r["split"],
            "o2a_ms": round((hit["_t_alert"] - t0 - on) * 1000) if hit and on is not None and r["label"] != "normal" else None,
            "false_alarms": len(pre), "wrong_cat": sum(e["category"] != r["label"] for e in opened if e not in pre),
            "normal_s": r["duration_s"] if r["label"] == "normal" else (on or 0),
            "alerts": [(e["category"], round(e["start_ts"] - t0, 1), round(e["peak_confidence"], 2)) for e in opened]}


def score_replay(rows):
    """Clip macro F1 (labels present), right, false alarms (events on normal footage: normal clips + before onset)
    per camera-hour, onset -> alert p50/max over right clips."""
    labs = sorted({r["label"] for r in rows} | {r["pred"] for r in rows})
    f1 = statistics.mean([2 * sum(r["label"] == L == r["pred"] for r in rows) /
                          max(1, sum((r["label"] == L) + (r["pred"] == L) for r in rows)) for L in labs])
    o2a = sorted(r["o2a_ms"] for r in rows if r["o2a_ms"] is not None and r["pred"] == r["label"])
    fa, hours = sum(r["false_alarms"] for r in rows), sum(r["normal_s"] for r in rows) / 3600
    inc = [r for r in rows if r["label"] != "normal"]
    def per_label(L):                                    # "right/n" + onset -> alert ms of the right ones
        mine = [r for r in rows if r["label"] == L]
        o2a = sorted(r["o2a_ms"] for r in mine if r["pred"] == L and r["o2a_ms"] is not None)
        return f"{sum(r['pred'] == L for r in mine)}/{len(mine)}" + (f" o2a {o2a}" if o2a else "")
    per = {L: per_label(L) for L in sorted({r["label"] for r in rows})}
    return {"n": len(rows), "right": sum(r["label"] == r["pred"] for r in rows), "macro_f1": round(f1, 3),
            "per_label": per,
            "incident_recall": f"{sum(r['pred'] != 'normal' for r in inc)}/{len(inc)}",   # alerted at all, any category
            "incident_precision": f"{sum(r['pred'] != 'normal' for r in inc)}/{sum(r['pred'] != 'normal' for r in rows)}",
            "false_alarms": fa, "fa_per_cam_hour": round(fa / hours, 1) if hours else None,
            "wrong_cat_alerts": sum(r["wrong_cat"] for r in rows),
            "o2a_p50_ms": pct(o2a, .5), "o2a_max_ms": o2a[-1] if o2a else None}


def call_truth(r, x):
    """A call's true label: the clip's label once its newest frame is past the onset, else normal."""
    on = r["onset_s"]
    return r["label"] if r["label"] != "normal" and on is not None and x["ts"] - r["t_first"] >= on else "normal"


def confusion(recs, probs=None):
    """Per model call (the VLM's own skill, before any event rule): true label -> {predicted top: n}."""
    m = defaultdict(lambda: defaultdict(int))
    for clip, r in recs.items():
        for i, x in enumerate(c for c in r["calls"] if "cam" in c):
            p = ((probs or {}).get(clip) or {}).get(i, x["p"])
            m[call_truth(r, x)][max(p, key=p.get)] += 1
    return {t: dict(sorted(v.items(), key=lambda kv: -kv[1])) for t, v in sorted(m.items())}


SWEEP = {"open_single_critical": [0.6, 0.65, 0.7, 0.75, 0.8, 0.85], "open_single_other": [0.75, 0.8, 0.85, 0.9, 0.95],
         "open_window": [0.45, 0.5, 0.55, 0.6, 0.65, 0.7], "open_window_ungated": [0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65],
         "corroborate_boost": [1.0, 1.1, 1.15, 1.25], "contradict_factor": [0.3, 0.5, 0.7, 1.0],
         "window_n": [2, 3, 4], "calibration_T": [0.7, 0.85, 1.0, 1.25, 1.5]}


def evaluate(recs, split, over=None, probs=None):
    """Replay every recording of the split with config overrides -> (score, rows). Restores the config after."""
    E, old = CFG["events"], dict(CFG["events"])
    E.update(over or {})
    try:
        rows = [replay(r, (probs or {}).get(c)) for c, r in recs.items() if split in (r["split"], "all")]
    finally:
        E.clear(); E.update(old)
    return score_replay(rows), rows


def sweep(tag, probs=None):
    """Each event threshold alone over its grid, on the dev split (tuning) with the test split beside it (never used
    to choose). Choice rule (D86): no more dev false alarms than now, then max dev macro F1, then lowest dev
    onset -> alert p50, then the current value."""
    recs = load_recs(tag)
    base = {s: evaluate(recs, s, probs=probs)[0] for s in ("dev", "test")}
    print("current:", json.dumps(base))
    best = {}
    for k, grid in SWEEP.items():
        cur, rows = CFG["events"][k], []
        for v in grid:
            d, t = evaluate(recs, "dev", {k: v}, probs)[0], evaluate(recs, "test", {k: v}, probs)[0]
            rows.append((v, d, t))
            print(f"{k:>22} {v:<5} dev F1 {d['macro_f1']:.3f} right {d['right']}/{d['n']} FA {d['false_alarms']} "
                  f"wrong-cat {d['wrong_cat_alerts']} o2a p50 {d['o2a_p50_ms']} | test F1 {t['macro_f1']:.3f} "
                  f"right {t['right']}/{t['n']} FA {t['false_alarms']} o2a p50 {t['o2a_p50_ms']}", flush=True)
        ok = [x for x in rows if x[1]["false_alarms"] <= base["dev"]["false_alarms"]]
        v, d, t = min(ok, key=lambda x: (-x[1]["macro_f1"], x[1]["o2a_p50_ms"] or 1e9, abs(x[0] - cur)))
        best[k] = v
        print(f"{'':>22} -> {k} = {v} (now {cur})\n", flush=True)
    return best


def reask(tag):
    """Every recorded mosaic re-classified with the CURRENT prompt (vlm.SYSTEM, e.g. after editing vlm.TABLE), same
    detector hints, stopped at the category (~1.3 s a call, GPU only, no YOLO, no playback).
    Returns {clip: {call index: probs}} for confusion() / evaluate(probs=...)."""
    out = {}
    for clip, r in load_recs(tag).items():
        for i, x in enumerate(c for c in r["calls"] if "cam" in c):
            if x.get("mosaic"):
                res = vlm.call(base64.b64encode((ROOT / x["mosaic"]).read_bytes()).decode(), x["hints"], on_decide=lambda *a: True)
                if res["probs"]:
                    out.setdefault(clip, {})[i] = {c: round(v, 5) for c, v in res["probs"].items()}
        print(clip, len(out.get(clip, {})), "calls re-asked", flush=True)
    return out


def show(tag, probs=None):
    """--replay: per-clip predictions, scores per split and the per-call confusion."""
    recs = load_recs(tag)
    for s in ("dev", "test"):
        sc, rows = evaluate(recs, s, probs=probs)
        for r in rows:
            print(f"{s:<4} {r['clip']:<24} {r['label']:<19} -> {r['pred']:<19} {'ok ' if r['label'] == r['pred'] else 'BAD'} "
                  f"o2a {r['o2a_ms']}  FA {r['false_alarms']}  alerts {r['alerts'][:4]}")
        print(s, json.dumps(sc), "\n")
    print("per-call confusion (true label -> model's top category):")
    for t, v in confusion(recs, probs).items():
        print(f"  {t:<19} {v}")


def score(rows):
    """Macro F1 over the labels present (truth or prediction), incident-vs-normal recall/precision, false alarms
    on normal clips, latency percentiles, errors grouped by confusion pair."""
    labs = sorted({r["label"] for r in rows} | {r["pred"] for r in rows})
    f1s = []
    for L in labs:
        tp = sum(r["label"] == L and r["pred"] == L for r in rows)
        fp = sum(r["label"] != L and r["pred"] == L for r in rows)
        fn = sum(r["label"] == L and r["pred"] != L for r in rows)
        f1s.append(2 * tp / (2 * tp + fp + fn) if tp + fp + fn else 1.0)
    inc = lambda x: x != "normal"
    tp = sum(inc(r["label"]) and inc(r["pred"]) for r in rows)
    errs = {}
    for r in rows:
        if r["label"] != r["pred"]:
            errs.setdefault(f"{r['label']} -> {r['pred']}", []).append(f"{r['clip']} ({r['keyframe']})")
    lat = [r["start_to_alert_ms"] for r in rows if r["start_to_alert_ms"] is not None and r["pred"] == r["label"]]
    t2a = [r["trigger_to_alert_ms"] for r in rows if r["trigger_to_alert_ms"] is not None and r["pred"] == r["label"]]
    # Onset -> alert, split: a clip whose incident starts before the first full mosaic (mosaic_span_s) also times the
    # buffer filling, which never happens on a running camera; the headline is the steady-state group.
    o2a = [(r["onset_to_alert_ms"], r["onset_s"]) for r in rows if r.get("onset_to_alert_ms") is not None and r["pred"] == r["label"]]
    steady = [ms for ms, on in o2a if on >= V["mosaic_span_s"]]
    mid = [ms for ms, on in o2a if on < V["mosaic_span_s"]]
    return {"n": len(rows), "right": sum(r["label"] == r["pred"] for r in rows), "macro_f1": round(statistics.mean(f1s), 3),
            "labels_in_f1": labs,
            "incident_recall": round(tp / max(1, sum(inc(r["label"]) for r in rows)), 3),
            "incident_precision": round(tp / max(1, sum(inc(r["pred"]) for r in rows)), 3) if any(inc(r["pred"]) for r in rows) else None,
            "false_alarms_normal": sum(not inc(r["label"]) and inc(r["pred"]) for r in rows),
            "start_to_alert_p50_p95": (pct(lat, .5), pct(lat, .95)), "trigger_to_alert_p50_p95": (pct(t2a, .5), pct(t2a, .95)),
            "onset_to_alert_p50_p95": (pct(steady, .5), pct(steady, .95)), "onset_to_alert_n": len(steady),
            "onset_to_alert_mid_start_p50_p95": (pct(mid, .5), pct(mid, .95)), "onset_to_alert_mid_start_n": len(mid),
            "errors": errs}


def per_clip(variant, rows_all, tots, split="dev"):
    """Each clip of the split alone through the real pipeline, played once."""
    rows = []
    for path, label in clips(split):
        r, t = run([path], tag=variant.replace(':', '_'))
        rows += [{"variant": variant, **x} for x in r]
        tots.setdefault(variant, []).append(t["gpu_duty"])
        print(variant, {k: rows[-1][k] for k in ("clip", "label", "pred", "confidence", "top3", "start_to_alert_ms",
                                                  "trigger_to_alert_ms", "gate_fired", "vetoes")}, flush=True)
    rows_all += rows
    return rows


def report(test, rows_all, tots):
    write(test, rows_all)
    out = {}
    for v in dict.fromkeys(r["variant"] for r in rows_all):
        out[v] = score([r for r in rows_all if r["variant"] == v]) | {"gpu_duty_mean": round(statistics.mean(tots[v]), 3)}
    (OUT / f"ab_{test}_summary.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    return out


def test_model():
    rows, tots = [], {}
    base = V["model"]
    for m in (base, "qwen3.5:2b"):
        V["model"] = m
        per_clip(m, rows, tots)
    V["model"] = base
    return report("model", rows, tots)


def test_tiles():
    rows, tots = [], {}
    per_clip("mosaic", rows, tots)
    V["p1_crop"]["enabled"] = True
    per_clip("person_crop", rows, tots)
    V["p1_crop"]["enabled"] = False
    # Native video: the 4 frames as 4 separate full-size images (576x320 each, letterboxed) in one call.
    mosaic, system, tile = vlm.mosaic, vlm.SYSTEM, V["tile"]
    def frames_as_images(frames, track_ids=()):
        grid, _ = mosaic(frames)
        imgs = [vlm.letterbox(f[1], 2 * tile[0], 2 * tile[1]) for f in frames]
        return grid, [vlm.base64.b64encode(vlm.cv2.imencode(".jpg", i, [vlm.cv2.IMWRITE_JPEG_QUALITY, 85])[1]).decode()
                      for i in imgs]
    vlm.mosaic = frames_as_images
    vlm.SYSTEM = system.replace("The image is a 2x2 grid of 4 frames in time order (top-left, top-right, bottom-left, "
                                "bottom-right) spanning about 2 seconds", "The images are 4 frames in time order spanning about 2 seconds")
    assert vlm.SYSTEM != system
    try:
        per_clip("native_video", rows, tots)
    finally:
        vlm.mosaic, vlm.SYSTEM = mosaic, system
    return report("tiles", rows, tots)


def write(test, rows):
    OUT.mkdir(parents=True, exist_ok=True)
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(OUT / f"ab_{test}.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, keys)
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    for f in ("model", "gate", "tiles", "check", "dev", "test"):
        ap.add_argument("--" + f, action="store_true")
    ap.add_argument("--run", nargs="+"); ap.add_argument("--seconds", type=float); ap.add_argument("--tag", default="x")
    ap.add_argument("--replay", metavar="TAG", help="re-score a recorded pass offline (no GPU)")
    ap.add_argument("--sweep", metavar="TAG", help="each event threshold over its grid on the recorded dev split")
    ap.add_argument("--reask", metavar="TAG", help="re-classify its recorded mosaics with the current prompt (GPU)")
    ap.add_argument("--probs", metavar="NAME", help="--replay/--sweep with data/ab/TAG/reask_NAME.json; --reask saves it")
    ap.add_argument("--duty-target", type=float, help="override vlm.duty_target (e.g. 1.01 = no back-off, the 'before')")
    a = ap.parse_args()
    if a.duty_target is not None:
        V["duty_target"] = a.duty_target
    if a.gate:
        check_gates() if a.check else test_gate()
    if a.model:
        test_model()
    if a.tiles:
        test_tiles()
    if a.dev:   # the headline pass: every dev clip alone, played once -> ab_dev_<tag>.csv + _summary.json
        rows, tots = [], {}
        per_clip(a.tag, rows, tots)
        report(f"dev_{a.tag}", rows, tots)
    if a.test:  # the held-out pass (P8): every test clip alone -> ab_test_<tag>.csv + _summary.json
        rows, tots = [], {}
        per_clip(a.tag, rows, tots, "test")
        report(f"test_{a.tag}", rows, tots)
    if a.reask:
        P = reask(a.reask)
        (ROOT / "data" / "ab" / a.reask / f"reask_{a.probs or 'now'}.json").write_text(json.dumps(P))
        show(a.reask, P)
    for t in (a.replay, a.sweep):
        if t and a.probs:
            P = {c: {int(i): p for i, p in v.items()} for c, v in
                 json.loads((ROOT / "data" / "ab" / t / f"reask_{a.probs}.json").read_text()).items()}
    if a.replay:
        show(a.replay, P if a.probs else None)
    if a.sweep:
        print(json.dumps(sweep(a.sweep, P if a.probs else None)))
    if a.run:
        rows, tot = run(a.run, a.seconds, a.tag)
        write(f"run_{a.tag}", rows)
        (OUT / f"ab_run_{a.tag}_totals.json").write_text(json.dumps(tot, indent=1))
        for r in rows:
            print(r)
        print(json.dumps(tot, indent=1))
