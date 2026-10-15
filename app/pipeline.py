"""Pipeline: capture -> detect -> gates/scheduler -> arbiter -> VLM (early decision) -> events -> SQLite (SPEC §5, §5a.1).

  uv run python -m app.pipeline                     cameras from config.yaml, runs until Ctrl-C
  uv run python -m app.pipeline a.mp4 [b.mp4 ...]   one camera per clip, played once; prints alerts, then per clip:
                                                    label, prediction, right/wrong and onset-to-alert ms (§12), plus
                                                    GPU duty, baselines skipped, vetoes and model latencies
      --label L --onset S   label/onset for a single clip (default: bench/labels.csv: clip,label,split,onset_s)
      --seconds N           loop the clips for N s instead (GPU-duty runs)
      --out file.json       also write the summary there
"""
import argparse
import csv
import json
import statistics
import sys
import threading
import time
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

from app import vlm
from app.config import CFG, ROOT
from app.db import DB
from app.detect import Detector
from app.events import EventManager
from app.ingest import Camera
from app.models import Arbiter
from app.scheduler import Scheduler, persons

V = CFG["vlm"]
DATA = ROOT / "data"


def ms(a, b):
    return round((b - a) * 1000) if a is not None and b is not None else None


class Pipeline:
    def __init__(self, cameras, loop=True, emit=None):
        self.emit = emit or self.print_emit
        self.db = DB()
        if CFG["replay"]["reset_live_tables_on_start"]:
            self.db.reset_live()
        self.cams = {c["id"]: Camera(c["id"], c["name"], c["source"], loop, c.get("door_zone"), c.get("watch_zone"))
                     for c in cameras}
        self.events = EventManager(self.db, self.emit, {c["id"]: c["name"] for c in cameras})
        self.arb = Arbiter(self.run_call)
        self.sched = Scheduler(self.arb, self.events)
        self.dets = {cid: Detector(cam, on_frame=self.sched.on_frame) for cid, cam in self.cams.items()}
        self.n_base, self.down_since = defaultdict(int), {}
        self.alerts, self.calls, self.vetoes = [], [], []
        self.vlm_errors = self.err_streak = 0
        self.veto_log = open(DATA / "veto_log.jsonl", "a")

    def start(self):
        _, b64 = vlm.mosaic([(0, np.full((360, 640, 3), 114, np.uint8), [])])
        vlm.call(b64, "Warm-up.")                       # E-3: model loaded before the first frame
        self.arb.start()
        for d in self.dets.values():
            d.start()
        for c in self.cams.values():
            c.start()
        threading.Thread(target=self._ticker, daemon=True, name="events-tick").start()
        self.t0 = time.time()

    def add_camera(self, c, loop=False):
        """Runtime camera (FR-5 upload): same objects as __init__, started at once."""
        cam = Camera(c["id"], c["name"], c["source"], loop, c.get("door_zone"), c.get("watch_zone"))
        self.events.cam_names[c["id"]] = c["name"]
        self.cams[c["id"]], self.dets[c["id"]] = cam, Detector(cam, on_frame=self.sched.on_frame)
        self.dets[c["id"]].start(); cam.start()
        return cam

    def remove_camera(self, cid):
        """Stop a camera; it counts as down from the epoch, so the next tick closes its open events (E-13)."""
        for x in (self.cams.pop(cid, None), self.dets.pop(cid, None)):
            if x:
                x.stop()
        self.down_since[cid] = 0

    def _ticker(self):
        while True:
            time.sleep(1)
            for cid, c in list(self.cams.items()):
                if c.status in ("reconnecting", "down", "ended"):   # an ended clip/upload closes its events (E-13)
                    self.down_since.setdefault(cid, time.time())
                else:
                    self.down_since.pop(cid, None)
            self.events.tick(down_since=self.down_since)

    def run_call(self, req):
        cam, det = req["cam"], self.dets.get(req["cam"])
        if det is None:                                     # camera removed while the request waited
            return
        base = req["prio"] == 3
        if base:  # P3: mosaic from the freshest buffer frames, built now (§5a step 5)
            frames = vlm.pick_frames(det.buffer)
            if not frames:
                return
            req.update(frames=frames, evidence=self.sched.evidence(det, frames[-1][0]), hint=None,
                       track_ids=[t["id"] for t in persons(frames[-1])])
            self.n_base[cam] += 1
        frames, ev = req["frames"], req["evidence"]
        newest = frames[-1]
        self.sched.note_call(cam, newest)
        delayed = time.time() - req["created"] > V["trigger_max_age_s"]
        crop = vlm.track_crop(newest, req["track_ids"]) is not None if V["p1_crop"]["enabled"] and not base else False
        grid, b64 = vlm.mosaic(frames, req["track_ids"] if crop else ())
        hints = f"Detector: up to {ev['max_persons']} people in the last 4 s. Gate: {req['hint'] or 'no trigger'}."
        if crop:
            hints += " The bottom-right tile is a close-up of those tracks in the newest frame."   # FR-9c
        summary_turn = base and self.n_base[cam] % V["summary_every_n"] == 1   # 1st, 4th, 7th... baseline (D42)
        st = {}

        def on_decide(probs, cat, sub, t_cat):
            c, vetoes = vlm.cross_check(vlm.calibrate(probs), ev)
            for cat_v, before, after in vetoes:
                v = {"ts": time.time(), "camera_id": cam, "category": cat_v, "p_before": before, "p_after": after,
                     "trigger": req["trigger"], "max_persons": ev["max_persons"]}
                self.vetoes.append(v)
                self.veto_log.write(json.dumps(v) + "\n"); self.veto_log.flush()
                if before >= 0.3:
                    self.emit("veto", v)
            opened, supported = self.events.decide(cam, c, sub, ev["triggers"], newest[0], req["created"])
            for e in opened:
                self.alerts.append((cam, e["category"], e["_t_alert"], e))
            st.update(c=c, evs=opened + supported, top=max(c, key=c.get), t_cat=t_cat)
            # D67: a P1 that agrees with an event already open on this camera only updates it, no summary
            if req["prio"] == 1 and st["top"] in {e["category"] for e in supported}:
                return True
            # FR-8a: a confident-normal verdict stops at the category (baselines except every Nth; all P1s, D61)
            return (req["prio"] == 1 or not summary_turn) and st["top"] == "normal" and c["normal"] >= 0.80

        def stop_at():
            if base and st.get("top") == "normal":
                return 12                                   # summary baseline: ~12 words (D42)
            if req["prio"] == 1 and self.arb.waiting(1):
                return 15                                   # another incident waits (FR-8a)
            return None

        try:
            r = vlm.call(b64, hints, on_decide, stop_at, req["cancel"])
        except Exception as e:                              # E-5: no observation, camera gets its next window
            self.vlm_errors += 1; self.err_streak += 1
            print(f"[vlm_error] {cam} P{req['prio']}: {e!r}", flush=True)
            return
        self.err_streak = 0
        if req.get("kind") == "horizontal" and st.get("top") == "normal" and st["c"]["normal"] >= 0.80:
            self.sched.silence(cam, req["track_ids"], newest[0])   # D61: don't re-ask about the same wide box
        if req.get("rule") == "fighting" and st.get("top") == "normal" and st["c"]["normal"] >= 0.80:
            self.sched.silence_pair(cam, req["track_ids"], det.person_hists(), newest[0])   # D64: people passing by
        if r["stopped"] == "cancelled" and "c" not in st:
            self.calls.append({"prio": req["prio"], "cam": cam, "stopped": "cancelled"})
            return                                          # preempted before the category: nothing observed
        c = st.get("c")
        ts = newest[0]
        obs = {"camera_id": cam, "ts": ts, "category": r["category"], "subtype": r["subtype"],
               "confidence": round(c[r["category"]], 3) if c and r["ok"] else 0.0,
               "probs": {k: round(v, 4) for k, v in c.items()} if c else None, "summary": r["summary"],
               "people_count": r["people_count"], "trigger": req["trigger"], "track_ids": req["track_ids"],
               "model": V["model"],
               "timing": {"t_capture": ts, "t_gate": req["created"] if not base else None, **r["timing"]}}
        thumb = DATA / "thumbs" / cam / f"{ts:.2f}.jpg"
        thumb.parent.mkdir(parents=True, exist_ok=True)
        f = newest[1]
        cv2.imwrite(str(thumb), cv2.resize(f, (320, round(f.shape[0] * 320 / f.shape[1]))))
        obs["thumb_path"] = str(thumb.relative_to(ROOT))

        def keyframes(eid):
            k = DATA / "keyframes"
            k.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(k / f"{eid}_0.jpg"), f); cv2.imwrite(str(k / f"{eid}_mosaic.jpg"), grid)
            return [f"data/keyframes/{eid}_0.jpg", f"data/keyframes/{eid}_mosaic.jpg"]

        obs["event_id"] = self.events.finish(cam, obs, st.get("evs", []), keyframes)
        obs["timing"]["t_db_write"] = time.time()
        obs["id"] = self.db.insert("observations", obs)
        t = obs["timing"]
        self.calls.append({"prio": req["prio"], "cam": cam, "stopped": r["stopped"], "delayed": delayed, "ok": r["ok"],
                           "category": r["category"], "c": obs["confidence"], "summary_turn": summary_turn,
                           "model_tta_ms": ms(ts, t.get("t_category")), "queue_ms": ms(req["created"], t["t_vlm_start"]),
                           "call_ms": ms(t["t_vlm_start"], t["t_vlm_done"]), "prompt_eval_count": r["prompt_eval_count"]})
        self.emit("trace", {"camera_id": cam, "trigger": req["trigger"], "created": req["created"], "timing": t,
                            "hints": hints, "raw_json": r.get("raw"), "mosaic_b64": b64})   # Workflow view (FR-15)
        self.emit("observation", obs)

    def print_emit(self, kind, d):
        now = time.strftime("%H:%M:%S")
        if kind == "alert":
            top3 = ", ".join(f"{k} {v:.2f}" for k, v in d["_probs"])
            print(f"{now} ALERT  {d['camera_id']} {d['category']} ({d['severity']}) c={d['peak_confidence']:.2f} "
                  f"trigger→alert {d['time_to_alert_ms']} ms  [{top3}]", flush=True)
        elif kind == "event_close":
            print(f"{now} CLOSE  {d['camera_id']} {d['category']} #{d['id']} n_obs={d['n_obs']}: {d['summary']}", flush=True)
        elif kind == "veto":
            print(f"{now} VETO   {d['camera_id']} {d['category']} {d['p_before']} -> {d['p_after']} "
                  f"(max persons {d['max_persons']})", flush=True)
        elif kind == "observation":
            o = d
            print(f"{now} obs    {o['camera_id']} {o['trigger']:<17} {o['category']:<19} c={o['confidence']:.2f} "
                  f"{(o['summary'] or '')[:90]}", flush=True)

    def stop(self):
        for c in self.cams.values():
            c.stop()
        for d in self.dets.values():
            d.stop()
        self.arb.stop()


def pct(xs, q):
    xs = sorted(x for x in xs if x is not None)
    return xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))] if xs else None


def load_labels():
    """bench/labels.csv -> {clip file name: (label, onset_s or None)} (FR-21)."""
    lf = ROOT / "bench" / "labels.csv"
    return {Path(r["clip"]).name: (r["label"], float(r["onset_s"]) if r.get("onset_s") else None)
            for r in csv.DictReader(open(lf))} if lf.exists() else {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clips", nargs="*")
    ap.add_argument("--label"); ap.add_argument("--onset", type=float)
    ap.add_argument("--seconds", type=float); ap.add_argument("--out")
    a = ap.parse_args()
    labels = load_labels()
    if a.label:
        labels[Path(a.clips[0]).name] = (a.label, a.onset)
    cams = [{"id": f"cam{i + 1}", "name": Path(c).name, "source": c} for i, c in enumerate(a.clips)] or CFG["cameras"]
    p = Pipeline(cams, loop=bool(a.seconds) or not a.clips)
    p.start()
    try:
        if a.seconds:
            time.sleep(a.seconds)
        elif a.clips:
            while any(c.status not in ("ended", "down", "stopped") for c in p.cams.values()):
                time.sleep(0.2)
            while p.arb.waiting() or p.arb.running:          # let queued calls on the last frames finish
                time.sleep(0.2)
        else:
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        pass
    t_end = time.time()
    p.events.close_all()
    p.stop()

    duty = p.arb.duty(window=t_end - p.t0, now=t_end)
    full = [c for c in p.calls if c.get("call_ms") is not None]
    out = {"model": V["model"], "cameras": len(cams), "wall_s": round(t_end - p.t0, 1), "gpu_duty": round(duty, 3),
           "calls": {f"P{k}": sum(1 for c in p.calls if c["prio"] == k) for k in (1, 3)},
           "stopped_at_category": sum(1 for c in p.calls if c.get("stopped") == "category"),
           "cancelled": sum(1 for c in p.calls if c.get("stopped") == "cancelled"),
           "baselines_skipped": p.sched.skipped, "gate_triggers": p.sched.n_triggers, "vlm_errors": p.vlm_errors,
           "vetoes": sum(1 for v in p.vetoes if v["p_before"] >= 0.3), "vetoes_logged": len(p.vetoes),   # D63
           "model_tta_ms": {"p50": pct([c["model_tta_ms"] for c in full], .5), "p95": pct([c["model_tta_ms"] for c in full], .95)},
           "call_ms": {"p50": pct([c["call_ms"] for c in full], .5), "p95": pct([c["call_ms"] for c in full], .95)},
           "queue_ms": {"p50": pct([c["queue_ms"] for c in full], .5), "p95": pct([c["queue_ms"] for c in full], .95)},
           "clips": []}
    for cid, c in p.cams.items():
        rows = p.db.rows("SELECT category, peak_confidence, summary, time_to_alert_ms FROM events WHERE camera_id=? "
                         "ORDER BY peak_confidence DESC", (cid,))
        pred = rows[0]["category"] if rows else "normal"
        label, onset = labels.get(Path(str(c.source)).name, (None, None))
        hit = next((t for cam, cat, t, _ in p.alerts if cam == cid and cat == label), None)
        o2a = ms(c.t_first + onset, hit) if hit and onset is not None and c.t_first else None
        out["clips"].append({"camera": cid, "clip": Path(str(c.source)).name, "label": label, "prediction": pred,
                             "right": None if label is None else pred == label, "onset_to_alert_ms": o2a,
                             "events": [(r["category"], round(r["peak_confidence"], 2), r["time_to_alert_ms"]) for r in rows],
                             "summary": rows[0]["summary"] if rows else None})
    print("\n" + json.dumps(out, indent=1))
    if a.out:
        Path(a.out).write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        main()
    else:  # self-check: the sample clip (people walking past a bus) end to end -> observations stored, no alert
        sys.argv += ["data/demo/sample_bus.mp4", "--label", "normal", "--out", str(DATA / "pipeline_selfcheck.json")]
        main()
        r = json.loads((DATA / "pipeline_selfcheck.json").read_text())
        db = DB()
        n = db.rows("SELECT count(*) n FROM observations")[0]["n"]
        assert n >= 2 and r["calls"]["P3"] >= 2 and r["vlm_errors"] == 0, (n, r)
        assert r["clips"][0]["right"], r["clips"][0]
        print("pipeline self-check ok:", n, "observations")
