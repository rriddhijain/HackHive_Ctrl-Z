"""Detector-side diagnosis on real clips (no model needed; CPU): what the detector and the gates see, and how often
the person_down second look (events.down_guard, D83) would be armed at a model call.

  uv run python -m bench.diagnose                 every dev clip -> bench/results/diag_<tag>.json + a table
  uv run python -m bench.diagnose CLIP --trace    one clip, frame by frame (frame idx, clip t, persons, horizontal, motion)

Replays the real Detector + Scheduler at 10 FPS in clip time with every model call answered at once (as
bench.ab --gate --check does). For each call it records the scheduler's evidence and the guard reason the event
manager would give a person_down verdict there (detector_blind / interaction / none). It does NOT run the vision model:
whether the model then says person_down, fighting or normal is only known from a real dev pass (bench.ab --dev).
"""
import argparse
import json
import threading
from types import SimpleNamespace as NS

import cv2

from app.config import CFG, ROOT
from app.gate import grey160, mad, wide

G, DET = CFG["gate"], CFG["detector"]
OUT = ROOT / "bench" / "results"


def replay(path, trace=False):
    from app.detect import Detector
    from app.events import EventManager
    from app.scheduler import Scheduler, persons

    class Instant:
        cv, running = threading.RLock(), None
        def __init__(self, on_call): self.on_call = on_call
        def waiting(self, prio=None, cam=None): return []
        def duty(self): return 0.0
        def submit(self, r): self.on_call(r); return r

    det = Detector(NS(id="diag", door_zone=None, watch_zone=None))
    guard = EventManager.guarded.__get__(NS())               # the event manager's own rule, no DB needed
    calls, frames, prev = [], [], None

    def on_call(r):
        newest = det.buffer[-1]
        sched.note_call("diag", newest)
        ev = sched.evidence(det, newest[0])
        calls.append({"t": round(newest[0], 1), "trigger": r["trigger"], "persons_now": len(persons(newest)),
                      "max_persons": ev["max_persons"], "person_frames_frac": ev["person_frames_frac"],
                      "pair_contact": ev["pair_contact"], "guard": guard(ev)})
    sched = Scheduler(Instant(on_call), NS(is_open=lambda c, k: False, has_open=lambda c: False))
    cap = cv2.VideoCapture(str(path))
    fps, i = cap.get(cv2.CAP_PROP_FPS) or 30, 0
    step = max(1, round(fps / DET["fps"]))
    while (got := cap.read())[0]:
        if i % step == 0:
            det._process(got[1], i / fps, i)
            sched.on_frame(det)
            e = det.buffer[-1]
            g = grey160(e[1])
            ps = persons(e)
            frames.append({"frame_idx": i, "clip_t": round(i / fps, 1), "persons": len(ps),
                           "ids_conf": [(t["id"], t["conf"]) for t in ps],
                           "horizontal": [t["id"] for t in ps if wide((0, *t["box"]), G)],
                           "motion_mad": round(mad(g, prev), 2) if prev is not None else 0.0})
            prev = g
        i += 1
    n = [f["persons"] for f in frames]
    mo = sorted(f["motion_mad"] for f in frames)
    out = {"clip": path.name, "duration_s": round(i / fps, 1), "frames": len(frames),
           "persons_max": max(n, default=0), "frames_with_person": sum(x > 0 for x in n),
           "frames_with_2plus": sum(x >= 2 for x in n), "frames_horizontal": sum(bool(f["horizontal"]) for f in frames),
           "motion_mad_p50": mo[len(mo) // 2] if mo else None, "motion_mad_p90": mo[int(0.9 * (len(mo) - 1))] if mo else None,
           "gate_fires": [{k: g[k] for k in ("clip_t", "rule", "kind", "persons", "outcome")} for g in sched.gate_log],
           "calls": calls, "calls_guarded": sum(c["guard"] is not None for c in calls),
           "guard_reasons": sorted({c["guard"] for c in calls if c["guard"]})}
    if trace:
        out["trace"] = frames
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clips", nargs="*"); ap.add_argument("--trace", action="store_true"); ap.add_argument("--tag", default="dev")
    a = ap.parse_args()
    from bench.ab import clips as dev_clips
    paths = [ROOT / c if not str(c).startswith("/") else c for c in a.clips] if a.clips else [p for p, _ in dev_clips()]
    from pathlib import Path
    res = [replay(Path(p), a.trace) for p in paths]
    print(f"{'clip':<24}{'dur':>6}{'pers max':>9}{'w/ person':>10}{'2+':>5}{'horiz':>6}{'motion p90':>11}"
          f"{'gate fires':>11}{'calls':>6}{'guarded':>8}  reasons")
    for r in res:
        print(f"{r['clip']:<24}{r['duration_s']:>6}{r['persons_max']:>9}{r['frames_with_person']:>6}/{r['frames']:<3}"
              f"{r['frames_with_2plus']:>5}{r['frames_horizontal']:>6}{r['motion_mad_p90']:>11}{len(r['gate_fires']):>11}"
              f"{len(r['calls']):>6}{r['calls_guarded']:>8}  {', '.join(r['guard_reasons']) or '-'}")
    if not a.clips:
        (OUT / f"diag_{a.tag}.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    elif a.trace:
        for f in res[0]["trace"]:
            print(f)


if __name__ == "__main__":
    main()
