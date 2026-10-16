"""Arbiter + scheduler under multi-camera load (synthetic, no model): simultaneous triggers, fairness, preemption,
stale drops, no duplicate pending P1 per camera, instrumentation; deterministic gate replay with synthetic tracks."""
import threading
import time
import unittest
from collections import deque
from types import SimpleNamespace as NS

import numpy as np

from app.models import Arbiter
from app.scheduler import Scheduler


def fake_call(log, ms=0.05):
    def run(req):
        for _ in range(int(ms / 0.005)):
            if req["cancel"].is_set():
                log.append((req["name"], "cancelled")); return
            time.sleep(0.005)
        log.append((req["name"], "done"))
    return run


def wait_idle(a, timeout=5):
    t = time.time()
    while (a.waiting() or a.running) and time.time() - t < timeout:
        time.sleep(0.01)
    time.sleep(0.02)


class ArbiterLoad(unittest.TestCase):
    def test_three_cameras_simultaneous_p1_round_robin(self):
        log = []
        a = Arbiter(fake_call(log)); a.start()
        a.submit({"prio": 3, "cam": "cam1", "name": "base"})          # running when the incidents arrive
        time.sleep(0.01)
        for k in range(2):
            for cam in ("cam1", "cam2", "cam3"):
                a.submit({"prio": 1, "cam": cam, "name": f"{cam}-{k}"})
        wait_idle(a)
        a.stop()
        self.assertEqual(log[0], ("base", "cancelled"))            # baseline preempted by the first P1
        served = [n for n, s in log[1:] if s == "done"]
        self.assertEqual(served, ["cam1-0", "cam2-0", "cam3-0", "cam1-1", "cam2-1", "cam3-1"])   # fair across cameras
        st = a.stats()
        self.assertEqual(st["by_priority"]["P1"]["n"], 6)
        self.assertEqual(st["by_priority"]["P3"]["cancelled"], 1)
        self.assertEqual(set(st["by_camera"]), {"cam1", "cam2", "cam3"})
        self.assertIsNotNone(st["by_camera"]["cam3"]["queue_ms"])

    def test_running_p1_never_cancelled(self):
        log = []
        a = Arbiter(fake_call(log, 0.1)); a.start()
        a.submit({"prio": 1, "cam": "cam1", "name": "p1a"}); time.sleep(0.02)
        a.submit({"prio": 1, "cam": "cam2", "name": "p1b"}); a.submit({"prio": 1, "cam": "cam3", "name": "p1c"})
        wait_idle(a); a.stop()
        self.assertEqual(log, [("p1a", "done"), ("p1b", "done"), ("p1c", "done")])

    def test_stale_relook_dropped_p1_never(self):
        log, dropped = [], []
        a = Arbiter(fake_call(log, 0.2), stale_s=0.1); a.start()
        a.submit({"prio": 1, "cam": "cam1", "name": "p1"}); time.sleep(0.02)
        a.submit({"prio": 4, "cam": "cam2", "name": "relook", "on_drop": dropped.append})
        a.submit({"prio": 1, "cam": "cam3", "name": "p1-old", "created": time.time() - 10})   # old P1: still served
        wait_idle(a); a.stop()
        self.assertEqual([n for n, _ in log], ["p1", "p1-old"])
        self.assertEqual([r["name"] for r in dropped], ["relook"])
        self.assertEqual(a.stats()["dropped_stale"], 1)

    def test_duty_timeline(self):
        a = Arbiter(lambda r: time.sleep(0.05)); a.start()
        for _ in range(3):
            a.submit({"prio": 3, "cam": "cam1"})
        wait_idle(a); a.stop()
        st = a.stats(window=60)
        self.assertEqual(len(st["duty_per_10s"]), 6)
        self.assertGreater(st["duty_last_60s"], 0)


class FakeArb:
    def __init__(self):
        self.cv, self.running, self.q = threading.RLock(), None, []
    def submit(self, r): self.q.append(r); return r
    def waiting(self, prio=None, cam=None):
        return [r for r in self.q if (prio is None or r["prio"] == prio) and (cam is None or r["cam"] == cam)]
    def duty(self): return 0.0


class FakeEvents:
    def is_open(self, cam, cat): return False
    def has_open(self, cam): return False


IMG = np.full((360, 640, 3), 120, np.uint8)


def lunge(t0):
    """Two people, one lunges into the other at the end: fires the fighting gate."""
    t = [t0 + i / 10 for i in range(11)]
    a = [(ti, 100, 100, 150, 300) for ti in t]
    x = [200 - 300 * max(0.0, ti - t0 - 0.7) for ti in t]
    return {1: a, 2: [(ti, xi, 100, xi + 50, 300) for ti, xi in zip(t, x)]}


def cam_det(cid):
    d = NS(cam=NS(id=cid), buffer=deque(maxlen=40), tracks={}, zones_norm={}, _last_idx=0)
    d.person_hists = lambda: {}
    return d


def step(s, det, t, hists=None):
    if hists is not None:
        det.person_hists = lambda: hists
    det._last_idx += 1
    det.buffer.append((t, IMG, [{"id": 1, "cls": "person", "box": (100, 100, 150, 300)},
                                {"id": 2, "cls": "person", "box": (140, 100, 190, 300)}]))
    s.on_frame(det)


class SchedulerLoad(unittest.TestCase):
    def test_no_duplicate_pending_p1_per_camera(self):
        arb = FakeArb(); s = Scheduler(arb, FakeEvents())
        dets = {c: cam_det(c) for c in ("cam1", "cam2", "cam3")}
        for c, d in dets.items():                                   # three cameras trigger together, repeatedly
            for k in range(5):
                step(s, d, 10.0 + k * 0.3, lunge(9.0 + k * 0.3))
        p1 = arb.waiting(1)
        self.assertEqual(sorted(r["cam"] for r in p1), ["cam1", "cam2", "cam3"])   # one each, refreshed not queued
        self.assertGreaterEqual(s.merged, 3)
        self.assertEqual(arb.waiting(3), [], "no baseline while a P1 waits")
        outcomes = {g["outcome"] for g in s.gate_log}
        self.assertTrue({"submitted", "merged"} <= outcomes, outcomes)

    def test_gate_log_fields(self):
        arb = FakeArb(); s = Scheduler(arb, FakeEvents()); d = cam_det("cam1")
        step(s, d, 10.0, lunge(9.0))
        g = s.gate_log[0]
        for k in ("frame_idx", "t_detector", "clip_t", "rule", "track_ids", "persons", "score", "outcome"):
            self.assertIn(k, g)
        self.assertEqual((g["rule"], g["track_ids"], g["persons"], g["outcome"]), ("fighting", [1, 2], 2, "submitted"))

    def test_deterministic_replay(self):
        def replay():
            arb = FakeArb(); s = Scheduler(arb, FakeEvents()); d = cam_det("cam1")
            for k in range(20):
                step(s, d, 10.0 + k * 0.1, lunge(9.0 + k * 0.1) if k % 7 == 0 else {})
            return [(g["frame_idx"], g["t_detector"], g["rule"], g["outcome"]) for g in s.gate_log], \
                   [(r["prio"], r["trigger"]) for r in arb.q]
        self.assertEqual(replay(), replay())
        log, q = replay()
        self.assertTrue(log and q)

    def test_evidence_blind_and_contact(self):
        arb = FakeArb(); s = Scheduler(arb, FakeEvents()); d = cam_det("cam1")
        for k in range(10):
            d.buffer.append((k / 10, IMG, []))
        d.buffer.append((1.0, IMG, [{"id": 1, "cls": "person", "box": (0, 0, 10, 10)}]))
        e = s.evidence(d, 1.0)
        self.assertTrue(e["detector_blind"])
        self.assertFalse(e["pair_contact"])
        step(s, d, 1.1)                                             # two overlapping boxes
        self.assertTrue(s.evidence(d, 1.1)["pair_contact"])


if __name__ == "__main__":
    unittest.main()
