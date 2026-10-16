"""Scheduler: turns gate triggers and the baseline timer into model requests (SPEC §5a steps 3–4, FR-8, D42, E-24).

on_frame(det) runs in each camera's detector thread after every frame:
  - gates (person tracks only, D54) + scene_change -> a P1 request with its 4 mosaic frames FROZEN at trigger time,
    unless an event of the rule's category is open there (cooldown) or the camera's last P1 was < 1 s ago.
    At most ONE P1 per camera in flight (D72): a trigger while that camera's P1 waits refreshes it to the newest frames
    (same rule: also its hint and tracks); a trigger while it runs is merged into it (counted, not queued). So false
    triggers never build a backlog, and a camera's newest moment is what its next call sees.
  - baseline: every 3 s (5 s with nobody in view) if no P1 waits anywhere -> a P3 request, unless change-gated:
    no open event, newest frame vs the frame of the camera's last model call MAD < 6, same person track IDs and none
    of their boxes moved or changed shape (D86: a small figure falling barely changes the MAD), < 8 s, and the last
    call wasn't an incident reading (top c >= relook.c_low that opened nothing: look again, don't wait 8 s, D86).
    While measured GPU duty (60 s) is above vlm.duty_target, baselines back off to one per camera per 15 s (D66).
    Gate-triggered P1s are never throttled and the arbiter serves them before any queued baseline.
  - a track whose "horizontal" person_down trigger got a confident-normal verdict (someone on a sofa, a close-up) is
    silenced until its box is clearly upright (D72), the track leaves, or horizontal_recheck_s passes (D61).
  - likewise a fight pair (people walking past each other): silenced until either track leaves, their centroid
    distance changes by > PAIR_REARM body heights, or horizontal_recheck_s passes (D64).
gate_log keeps every gate fire with its outcome (submitted / merged / cooldown / silenced / too_soon) and the frame
index, detector time, clip time, rule, track ids, person count and score, so offline replay and live runs can be
compared fire by fire. evidence() also reports how often the detector saw anyone (detector_blind) and whether two
person boxes touched in the buffer (pair_contact), for the person_down second look (events.down_guard).
"""
import math
import time
from collections import defaultdict, deque

from app.config import CFG
from app.gate import gap, gate, grey160, mad, overlap, scene_change, wide
from app.vlm import GATE_CAT, pick_frames

G, V, D = CFG["gate"], CFG["vlm"], CFG["detector"]
PAIR_REARM = 0.5   # body heights; a pair that closes in or separates by this much is asked about again (D64)
# A silenced wide track re-arms only once its box is clearly upright (< 0.8 × down_ratio wide per tall, D72): a seated
# close-up hovers at ~1.2 and re-armed on every 1.17 frame (14 horizontal ①s/min on 2 webcams, all normal).
UPRIGHT = 0.8
# D86: a baseline is skipped only if no person moved since the camera's last call. fall_a_view5: a fall across the room
# kept MAD < 6 and the same track ID, so 15 s passed with no look over the fall. A fall turns a tall box wide.
MOVED, RESHAPED = 0.5, 0.25   # body heights the centroid moved; fraction the box height or width/height ratio changed


def changed(a, b):
    """Person box a (camera's last call) vs b (now), both (x1, y1, x2, y2) pixels: moved or reshaped enough to look."""
    ha, hb = max(a[3] - a[1], 1), max(b[3] - b[1], 1)
    move = math.hypot(a[0] + a[2] - b[0] - b[2], a[1] + a[3] - b[1] - b[3]) / 2 / ha
    ra, rb = (a[2] - a[0]) / ha, (b[2] - b[0]) / hb
    return move >= MOVED or abs(hb - ha) >= RESHAPED * ha or abs(rb - ra) >= RESHAPED * ra


def upright(s):
    return s[3] - s[1] < UPRIGHT * G["down_ratio"] * (s[4] - s[2])


def persons(entry):
    return [t for t in entry[2] if t["cls"] == "person"]


class Scheduler:
    def __init__(self, arbiter, events):
        self.arb, self.events = arbiter, events
        self.recent = defaultdict(deque)   # camera -> recent triggers (for corroboration within the 4 s buffer)
        self.last_p1 = {}                  # camera -> time of its last P1 request
        self.last_call = {}                # camera -> (time, grey160 of the call's newest frame, {person id: box})
        self.suspect = {}                  # camera -> its last call read an incident (top c >= c_low) (D86)
        self.last_skip = {}
        self.quiet = {}                    # (camera, track id) -> time its horizontal trigger was silenced (D61)
        self.quiet_pairs = {}              # (camera, (i, j)) -> (time silenced, gap then) (D64)
        self.skipped = 0
        self.skipped_by = defaultdict(int)  # camera -> baselines skipped (change gate or duty back-off)
        self.skipped_duty = 0
        self.n_triggers = self.merged = 0
        self.gate_log = deque(maxlen=5000)  # every gate fire + outcome (P5 timing diagnostics)

    def evidence(self, det, now):
        """Detector evidence for the cross-check (E-7): person counts = max over the 4 s buffer (D46)."""
        buf = list(det.buffer)
        door_entries = sum(1 for tr in list(det.tracks.values()) if tr.cls == 0
                           for t in tr.zone_entries.get("door", []) if now - t <= D["buffer_s"])
        trig = {GATE_CAT[t["rule"]] for t in self.recent[det.cam.id] if t["rule"] in GATE_CAT and now - t["t"] <= D["buffer_s"]}
        seen = [len(persons(e)) for e in buf]
        frac = sum(n > 0 for n in seen) / len(seen) if seen else 0.0
        contact = any(overlap((0, *a["box"]), (0, *b["box"])) for e in buf
                      for i, a in enumerate(persons(e)) for b in persons(e)[i + 1:])
        return {"max_persons": max(seen, default=0), "door": "door" in det.zones_norm,
                "door_entries": door_entries, "triggers": trig,
                "person_frames_frac": round(frac, 2), "pair_contact": contact,
                "detector_blind": frac < CFG["events"].get("down_guard", {}).get("blind_frac", 0.5)}

    def on_frame(self, det):
        cam, buf = det.cam.id, det.buffer
        if not buf:
            return
        new = buf[-1]
        now = new[0]
        hists = det.person_hists()
        for k in [k for k in self.quiet if k[0] == cam and (k[1] not in hists or upright(hists[k[1]][-1]))]:
            del self.quiet[k]                                   # re-arm: box clearly upright, or the track left
        for k, (t0, g0) in list(self.quiet_pairs.items()):
            i, j = k[1]
            if k[0] == cam and (i not in hists or j not in hists or now - t0 >= G["horizontal_recheck_s"]
                                or abs(gap(hists[i][-1], hists[j][-1]) - g0) > PAIR_REARM):
                del self.quiet_pairs[k]
        trigs = gate(cam, hists, G, skip={k[1] for k in self.quiet_pairs if k[0] == cam},
                     zones=getattr(det, "zones", None), buffer=buf, det_tracks=getattr(det, "tracks", None))
        old = next((e for e in reversed(buf) if now - e[0] >= 0.5), None)
        if old and (d := scene_change(old, new, G)):
            trigs.append({"camera_id": cam, "rule": "scene_change", "track_ids": [], "score": round(min(1.0, d * 2), 2),
                          "hint": f"the background changed abruptly in 0.5 s (mean pixel change {d:.0%}, people excluded) (possible scene change)"})
        rec = self.recent[cam]
        while rec and now - rec[0]["t"] > D["buffer_s"]:
            rec.popleft()
        for tr in trigs:
            tr["t"] = now
            rec.append(tr)
            self.trigger(det, tr, now)
        self.baseline(det, now)

    def _log(self, det, tr, now, outcome):
        t_first = getattr(det.cam, "t_first", None)
        self.gate_log.append({"frame_idx": getattr(det, "_last_idx", None), "t_detector": round(now, 3),
                              "clip_t": round(now - t_first, 2) if t_first else round(now, 2), "rule": tr["rule"],
                              "kind": tr.get("kind"), "track_ids": tr["track_ids"], "score": tr.get("score"),
                              "persons": len(persons(det.buffer[-1])) if det.buffer else 0, "outcome": outcome})

    def trigger(self, det, tr, now):
        cam, rule = det.cam.id, tr["rule"]
        if tr.get("kind") == "horizontal" and all(now - self.quiet.get((cam, i), -1e9) < G["horizontal_recheck_s"]
                                                  for i in tr["track_ids"]):
            return self._log(det, tr, now, "silenced")          # silenced after a confident-normal verdict (D61)
        if rule in GATE_CAT and self.events.is_open(cam, GATE_CAT[rule]):
            return self._log(det, tr, now, "cooldown")          # cooldown per (camera, category)
        req = {"prio": 1, "cam": cam, "rule": rule, "trigger": "gate:" + rule, "frames": pick_frames(det.buffer),
               "evidence": self.evidence(det, now), "hint": tr["hint"], "track_ids": tr["track_ids"], "kind": tr.get("kind"),
               "target_bbox": tr.get("target_bbox") or tr.get("bbox"), "bbox_a": tr.get("bbox_a"), "bbox_b": tr.get("bbox_b")}
        with self.arb.cv:                                       # ≤ 1 P1 per camera in flight (D72)
            waiting = self.arb.waiting(1, cam)
            if waiting:                                         # refresh it; the arbiter can't pick it meanwhile
                waiting[0].update(req if waiting[0]["rule"] == rule else {k: req[k] for k in ("frames", "evidence")})
            run = self.arb.running
            if waiting or (run and run["prio"] == 1 and run["cam"] == cam):
                self.merged += 1
                return self._log(det, tr, now, "merged")
        if now - self.last_p1.get(cam, 0) < 1.0:
            return self._log(det, tr, now, "too_soon")          # < 1 s since this camera's last P1
        self.last_p1[cam] = now
        self.n_triggers += 1
        self._log(det, tr, now, "submitted")
        self.arb.submit(req | {"created": time.time()})

    def baseline(self, det, now):
        cam = det.cam.id
        if self.arb.waiting(1) or self.arb.waiting(3, cam):
            return                                              # no P1 waiting anywhere; ≤ 1 pending baseline per camera
        anyone = any(persons(e) for e in det.buffer)
        interval = V["baseline_interval_s"] if anyone else V["empty_interval_s"]
        last = self.last_call.get(cam)
        if last and now - last[0] < interval:
            return
        if last and now - last[0] < V["baseline_skip"]["max_skip_s"]:
            new = det.buffer[-1]
            busy = self.arb.duty() > V["duty_target"]               # D66: back off while the GPU is saturated
            boxes = {t["id"]: t["box"] for t in persons(new)}
            still = last[2] is not None and boxes.keys() == last[2].keys() and not any(
                changed(last[2][i], b) for i, b in boxes.items())
            if busy or (not self.suspect.get(cam) and not self.events.has_open(cam) and still
                        and mad(grey160(new[1]), last[1]) < V["baseline_skip"]["mad"]):
                if now - self.last_skip.get(cam, 0) >= interval:   # one skip counted per baseline slot
                    self.skipped += 1; self.skipped_by[cam] += 1; self.skipped_duty += busy
                    self.last_skip[cam] = now
                return
        self.arb.submit({"prio": 3, "cam": cam, "rule": None, "trigger": "baseline", "created": time.time()})
        self.last_call[cam] = (now, None, None)                # placeholder until dispatch fills in the real frame

    def silence(self, cam, track_ids, now):
        for i in track_ids:
            self.quiet[(cam, i)] = now

    def silence_pair(self, cam, pair, hists, now):
        i, j = sorted(pair)
        if i in hists and j in hists:
            self.quiet_pairs[(cam, (i, j))] = (now, gap(hists[i][-1], hists[j][-1]))

    def note_call(self, cam, entry):
        """At dispatch: remember the frame this camera's model call sees (the change gate compares against it)."""
        self.last_call[cam] = (entry[0], grey160(entry[1]), {t["id"]: t["box"] for t in persons(entry)})


if __name__ == "__main__":
    import threading
    import numpy as np
    from types import SimpleNamespace as NS

    class FakeArb:
        cv, running = threading.RLock(), None
        def __init__(self): self.q = []
        def submit(self, r): self.q.append(r); return r
        def waiting(self, prio=None, cam=None): return [r for r in self.q if (prio is None or r["prio"] == prio) and (cam is None or r["cam"] == cam)]
        def drop(self, r): self.q.remove(r)
        def duty(self): return self.d
        d = 0.0
    class FakeEvents:
        open = set()
        def is_open(self, cam, cat): return (cam, cat) in self.open
        def has_open(self, cam): return any(c == cam for c, _ in self.open)

    arb, ev = FakeArb(), FakeEvents()
    s = Scheduler(arb, ev)
    img = np.full((360, 640, 3), 120, np.uint8)
    walker = {"id": 1, "cls": "person", "box": (100, 100, 150, 300)}
    det = NS(cam=NS(id="cam1"), buffer=deque(maxlen=40), tracks={}, zones_norm={}, person_hists=lambda: {})
    def step(t, frame=img, tracks=(walker,)):
        det.buffer.append((t, frame, list(tracks))); s.on_frame(det)
    # First frame -> a baseline; dispatch it; an unchanged scene is then skipped (counted once per 3 s slot)...
    step(0.0); assert [r["trigger"] for r in arb.q] == ["baseline"]
    arb.q.clear(); s.note_call("cam1", det.buffer[-1])
    cap = V["baseline_skip"]["max_skip_s"]
    for i in range(1, int(cap * 10)):
        step(i / 10)
    assert arb.q == [] and s.skipped == int((cap - 0.1) // 3), (arb.q, s.skipped)
    # ...but never longer than max_skip_s.
    step(cap)
    assert [r["trigger"] for r in arb.q] == ["baseline"], arb.q
    arb.q.clear(); s.note_call("cam1", det.buffer[-1]); t0 = cap
    # A new person appearing ends the skip at the next 3 s slot.
    other = {"id": 2, "cls": "person", "box": (300, 100, 350, 300)}
    for i in range(1, 31):
        step(t0 + i / 10, tracks=(walker, other))
    assert [r["trigger"] for r in arb.q] == ["baseline"], arb.q
    arb.q.clear(); s.note_call("cam1", det.buffer[-1]); t0 += 3
    # D86: so does the same person falling (same track ID, tall box -> wide box: MAD alone missed it)...
    down = {"id": 1, "cls": "person", "box": (80, 220, 220, 300)}
    assert changed(walker["box"], down["box"]) and not changed(walker["box"], (104, 96, 156, 300))
    for i in range(1, 31):
        step(t0 + i / 10, tracks=(down, other))
    assert [r["trigger"] for r in arb.q] == ["baseline"], arb.q
    arb.q.clear(); s.note_call("cam1", det.buffer[-1]); t0 += 3
    # ...and a last call that read an incident without opening one: the camera is looked at again at the next slot.
    s.suspect["cam1"] = True
    for i in range(1, 31):
        step(t0 + i / 10, tracks=(down, other))
    assert [r["trigger"] for r in arb.q] == ["baseline"], arb.q
    arb.q.clear(); s.suspect["cam1"] = False; s.note_call("cam1", (18.0, img, [walker]))   # last call at 18 s
    # A fall: the person_down gate fires -> P1 with frozen frames; repeat triggers are deduped while it waits.
    det.person_hists = lambda: {1: [(0.1 * i, 100, 100 + (i >= 8) * 100, 200, 300) for i in range(11)]}
    step(18.1); step(18.2)
    p1 = arb.waiting(1)
    assert len(p1) == 1 and p1[0]["trigger"] == "gate:person_down" and len(p1[0]["frames"]) == 4, p1
    # One P1 per camera in flight (D72): while it waits, a new trigger refreshes its frames instead of queueing...
    det.person_hists = lambda: {1: [(18.3 + 0.1 * i, 100, 100 + (i >= 8) * 100, 200, 300) for i in range(11)]}
    m0 = s.merged; step(19.4); p1 = arb.waiting(1)
    assert len(p1) == 1 and p1[0]["frames"][-1][0] == 19.4 and s.merged == m0 + 1, ([f[0] for f in p1[0]["frames"]], s.merged)
    # ...and while it runs, a trigger is merged into it (nothing new queued).
    arb.running = p1[0]; arb.q.clear(); step(20.6)
    assert not arb.waiting(1) and s.merged == m0 + 2, s.merged
    arb.running = None
    assert p1[0]["evidence"]["triggers"] == {"person_down"} and p1[0]["evidence"]["max_persons"] == 2
    # No baseline while a P1 waits; cooldown while a person_down event is open.
    assert not arb.waiting(3)
    arb.q.clear(); ev.open = {("cam1", "person_down")}; step(25.0)
    assert not arb.waiting(1)
    # Someone lying on a sofa: the horizontal trigger fires once; after a confident-normal verdict it stays quiet while
    # the box stays wide, re-arms when the person gets up (box no longer wide) or after horizontal_recheck_s.
    arb.q.clear(); ev.open = set()
    sofa = lambda t0: {3: [(t0 + 0.1 * i, 100, 250, 300, 320) for i in range(11)]}
    det.person_hists = lambda: sofa(30); step(31.0)
    assert [r["kind"] for r in arb.q] == ["horizontal"]; arb.q.clear(); s.silence("cam1", [3], 31.0)
    det.person_hists = lambda: sofa(32); step(33.0); assert not arb.waiting(1)
    det.person_hists = lambda: {3: [(33.1, 100, 150, 335, 350)]}; step(33.1)   # close-up dips to 1.17: still quiet (D72)
    assert ("cam1", 3) in s.quiet
    det.person_hists = lambda: sofa(31 + G["horizontal_recheck_s"]); step(32.0 + G["horizontal_recheck_s"])
    assert arb.waiting(1), "re-armed after horizontal_recheck_s"
    arb.q.clear(); s.silence("cam1", [3], 70.0)
    det.person_hists = lambda: {3: [(70.1, 150, 100, 200, 320)]}; step(70.1)   # stood up: re-armed
    assert ("cam1", 3) not in s.quiet
    # Duty back-off (D66): GPU above duty_target -> a changing scene still gets only one baseline per 15 s.
    det.person_hists = lambda: {}; step(100.0); arb.q.clear(); arb.d = 0.9; s.note_call("cam1", det.buffer[-1])
    for i in range(1001, 1000 + int(cap * 10)):
        step(i / 10, frame=np.full((360, 640, 3), 100 + 20 * (i % 2), np.uint8))   # MAD 20: changing, no scene_change
    assert not arb.waiting(3) and s.skipped_duty >= 2, s.skipped_duty   # one per 3 s slot up to max_skip_s
    step(100.0 + cap); assert arb.waiting(3), "max_skip_s still caps the back-off"
    arb.q.clear(); arb.d = 0.0
    # Two people walking past each other: fight trigger once; after a confident-normal verdict the pair stays quiet
    # while their distance holds, re-arms when they move apart or close in (D64).
    arb.q.clear(); s.last_p1.clear()
    walk = lambda t0, dx=0: {4: [(t0 + 0.1 * i, 100 + 30 * i, 100, 150 + 30 * i, 300) for i in range(8)],
                             5: [(t0 + 0.1 * i, 120 + 30 * i + dx, 100, 170 + 30 * i + dx, 300) for i in range(8)]}
    det.person_hists = lambda: walk(80); step(80.7)
    assert [r["rule"] for r in arb.q] == ["fighting"]; arb.q.clear(); s.silence_pair("cam1", [5, 4], walk(80), 80.7)
    det.person_hists = lambda: walk(82); step(82.7); assert not arb.waiting(1), "silenced pair"
    det.person_hists = lambda: walk(84, dx=-160); step(84.7)   # gap grew by 0.6 body heights -> re-armed
    det.person_hists = lambda: walk(84, dx=-20); step(86.7)
    assert [r["rule"] for r in arb.waiting(1)] == ["fighting"]
    print("scheduler self-check ok")
