"""P2b A/B tests on the dev clips (PLAN P2b, SPEC §12). One flag per test; results -> bench/results/ab_<test>.csv.

  uv run python -m bench.ab --model    qwen3.5 4B vs 2B, real pipeline + real prompt, one clip at a time, played once
  uv run python -m bench.ab --gate     plain yolo26n vs yolo26n-pose for the gates (FR-6a): detector replayed offline
                                       on every clip at 10 FPS in clip time; per clip: which rules fired, when, and the
                                       track values behind the ones that didn't (fight pair speed, overlap, persons seen)
  uv run python -m bench.ab --tiles    2x2 mosaic vs person-crop tile 4 (FR-9c) vs the 4 frames as separate images
  uv run python -m bench.ab --run a.mp4 [b.mp4 ...] [--seconds N] [--tag T]   one pipeline run (several clips = several
                                       cameras at once; --seconds loops them): per-camera rows -> ab_run_<tag>.csv
Rows: one per clip: clip, true label, predicted label, confidence, top-3, onset-to-alert ms (needs onset_s; else
start->alert = an upper bound), trigger->alert, gates fired, vetoes (p >= 0.3), key-frame path, calls, queue ms.
The printed summary groups errors by confusion pair with their key-frame paths.
"""
import argparse
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
from app.gate import _old_enough, gate, norm_speed

V = CFG["vlm"]

DET, G = CFG["detector"], CFG["gate"]
DEV = ROOT / "data" / "dev"
OUT = ROOT / "bench" / "results"


def clips():
    from app.pipeline import load_labels
    labels = load_labels()
    return [(p, labels.get(p.name, (p.parent.name, None))[0]) for p in sorted(DEV.glob("*/*")) if p.suffix in (".mp4", ".avi")]


def overlap(a, b):
    return min(a[3], b[3]) > max(a[1], b[1]) and min(a[4], b[4]) > max(a[2], b[2])


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


def pct(xs, q):
    xs = sorted(x for x in xs if x is not None)
    return xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))] if xs else None


def run(paths, seconds=None, tag="run"):
    """Real Pipeline (app.pipeline), one camera per clip, in this process. Played once unless seconds (looped).
    Returns (per-camera rows, run totals)."""
    from app.pipeline import Pipeline, load_labels
    labels = load_labels()
    cams = [{"id": f"cam{i + 1}", "name": Path(c).name, "source": str(c)} for i, c in enumerate(paths)]
    p = Pipeline(cams, loop=bool(seconds), emit=lambda k, d: None)
    subs, submit = [], p.arb.submit
    p.arb.submit = lambda r: (subs.append((r["cam"], r["trigger"], time.time())), submit(r))[1]
    p.start()
    if seconds:
        time.sleep(seconds)
    else:
        while any(c.status not in ("ended", "down", "stopped") for c in p.cams.values()):
            time.sleep(0.2)
        while p.arb.waiting() or p.arb.running:
            time.sleep(0.2)
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
        rows.append({"clip": Path(str(c.source)).name, "label": label, "pred": pred,
                     "confidence": round(best["peak_confidence"] if best else probs.get("normal", 0), 3),
                     "top3": " ".join(f"{k}:{v:.2f}" for k, v in sorted(probs.items(), key=lambda kv: -kv[1])[:3]),
                     "onset_to_alert_ms": round((hit - c.t_first - onset) * 1000) if hit and onset is not None else None,
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
    full = [x for x in p.calls if x.get("call_ms") is not None]
    tot = {"wall_s": round(wall, 1), "gpu_duty": round(p.arb.duty(window=wall, now=t_end), 3),
           "model_tta_p50": pct([x["model_tta_ms"] for x in full], .5), "call_ms_p50": pct([x["call_ms"] for x in full], .5),
           "gate_triggers": p.sched.n_triggers, "skipped": p.sched.skipped, "vlm_errors": p.vlm_errors,
           "vetoes_logged": len(p.vetoes), "vetoes_p_ge_0.3": sum(v["p_before"] >= 0.3 for v in p.vetoes),
           "alerts": [(cam, cat, round(e["time_to_alert_ms"])) for cam, cat, _, e in p.alerts]}
    return rows, tot


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
    return {"n": len(rows), "right": sum(r["label"] == r["pred"] for r in rows), "macro_f1": round(statistics.mean(f1s), 3),
            "labels_in_f1": labs,
            "incident_recall": round(tp / max(1, sum(inc(r["label"]) for r in rows)), 3),
            "incident_precision": round(tp / max(1, sum(inc(r["pred"]) for r in rows)), 3) if any(inc(r["pred"]) for r in rows) else None,
            "false_alarms_normal": sum(not inc(r["label"]) and inc(r["pred"]) for r in rows),
            "start_to_alert_p50_p95": (pct(lat, .5), pct(lat, .95)), "trigger_to_alert_p50_p95": (pct(t2a, .5), pct(t2a, .95)),
            "errors": errs}


def per_clip(variant, rows_all, tots):
    """Each dev clip alone through the real pipeline, played once."""
    rows = []
    for path, label in clips():
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
    for f in ("model", "gate", "tiles"):
        ap.add_argument("--" + f, action="store_true")
    ap.add_argument("--run", nargs="+"); ap.add_argument("--seconds", type=float); ap.add_argument("--tag", default="x")
    ap.add_argument("--duty-target", type=float, help="override vlm.duty_target (e.g. 1.01 = no back-off, the 'before')")
    a = ap.parse_args()
    if a.duty_target is not None:
        V["duty_target"] = a.duty_target
    if a.gate:
        test_gate()
    if a.model:
        test_model()
    if a.tiles:
        test_tiles()
    if a.run:
        rows, tot = run(a.run, a.seconds, a.tag)
        write(f"run_{a.tag}", rows)
        (OUT / f"ab_run_{a.tag}_totals.json").write_text(json.dumps(tot, indent=1))
        for r in rows:
            print(r)
        print(json.dumps(tot, indent=1))
