"""Scheduler: turns gate triggers and the baseline timer into model requests (SPEC §5a steps 3–4, FR-8, D42, E-24).

on_frame(det) runs in each camera's detector thread after every frame:
  - gates (person tracks only, D54) + scene_change -> a P1 request with its 4 mosaic frames FROZEN at trigger time,
    unless that camera already has a P1 for the same rule queued, an event of the rule's category is open there
    (cooldown), or the camera's last P1 was < 1 s ago. At most 3 waiting P1s per camera (oldest dropped beyond that).
  - baseline: every 3 s (10 s with nobody in view) if no P1 waits anywhere -> a P3 request, unless change-gated:
    no open event, newest frame vs the frame of the camera's last model call MAD < 6, same person track IDs, < 15 s.
  - a track whose "horizontal" person_down trigger got a confident-normal verdict (someone on a sofa, a close-up) is
    silenced until its box stops being wide, the track leaves, or horizontal_recheck_s passes (D61).
  - likewise a fight pair (people walking past each other): silenced until either track leaves, their centroid
    distance changes by > PAIR_REARM body heights, or horizontal_recheck_s passes (D64).
"""
import time
from collections import defaultdict, deque

from app.config import CFG
from app.gate import gap, gate, grey160, mad, scene_change, wide
from app.vlm import GATE_CAT, pick_frames

G, V, D = CFG["gate"], CFG["vlm"], CFG["detector"]
PAIR_REARM = 0.5   # body heights; a pair that closes in or separates by this much is asked about again (D64)


def persons(entry):
    return [t for t in entry[2] if t["cls"] == "person"]


class Scheduler:
    def __init__(self, arbiter, events):
        self.arb, self.events = arbiter, events
        self.recent = defaultdict(deque)   # camera -> recent triggers (for corroboration within the 4 s buffer)
        self.last_p1 = {}                  # camera -> time of its last P1 request
        self.last_call = {}                # camera -> (time, grey160 of the call's newest frame, person id set)
        self.last_skip = {}
        self.quiet = {}                    # (camera, track id) -> time its horizontal trigger was silenced (D61)
        self.quiet_pairs = {}              # (camera, (i, j)) -> (time silenced, gap then) (D64)
        self.skipped = 0
        self.n_triggers = 0

    def evidence(self, det, now):
        """Detector evidence for the cross-check (E-7): person counts = max over the 4 s buffer (D46)."""
        buf = list(det.buffer)
        door_entries = sum(1 for tr in list(det.tracks.values()) if tr.cls == 0
                           for t in tr.zone_entries.get("door", []) if now - t <= D["buffer_s"])
        trig = {GATE_CAT[t["rule"]] for t in self.recent[det.cam.id] if t["rule"] in GATE_CAT and now - t["t"] <= D["buffer_s"]}
        return {"max_persons": max((len(persons(e)) for e in buf), default=0), "door": "door" in det.zones_norm,
                "door_entries": door_entries, "triggers": trig}

    def on_frame(self, det):
        cam, buf = det.cam.id, det.buffer
        if not buf:
            return
        new = buf[-1]
        now = new[0]
        hists = det.person_hists()
        for k in [k for k in self.quiet if k[0] == cam and (k[1] not in hists or not wide(hists[k[1]][-1], G))]:
            del self.quiet[k]                                   # re-arm: box no longer wide, or the track left
        for k, (t0, g0) in list(self.quiet_pairs.items()):
            i, j = k[1]
            if k[0] == cam and (i not in hists or j not in hists or now - t0 >= G["horizontal_recheck_s"]
                                or abs(gap(hists[i][-1], hists[j][-1]) - g0) > PAIR_REARM):
                del self.quiet_pairs[k]
        trigs = gate(cam, hists, G, skip={k[1] for k in self.quiet_pairs if k[0] == cam})
        old = next((e for e in reversed(buf) if now - e[0] >= 0.5), None)
        if old and (d := scene_change(old, new, G)):
            trigs.append({"camera_id": cam, "rule": "scene_change", "track_ids": [], "score": round(min(1.0, d * 2), 2),
                          "hint": f"The scene changed suddenly ({d:.0%} of the picture) in 0.5 s."})
        rec = self.recent[cam]
        while rec and now - rec[0]["t"] > D["buffer_s"]:
            rec.popleft()
        for tr in trigs:
            tr["t"] = now
            rec.append(tr)
            self.trigger(det, tr, now)
        self.baseline(det, now)

    def trigger(self, det, tr, now):
        cam, rule = det.cam.id, tr["rule"]
        if tr.get("kind") == "horizontal" and all(now - self.quiet.get((cam, i), -1e9) < G["horizontal_recheck_s"]
                                                  for i in tr["track_ids"]):
            return                                              # silenced after a confident-normal verdict (D61)
        if rule in GATE_CAT and self.events.is_open(cam, GATE_CAT[rule]):
            return                                              # cooldown per (camera, category)
        queued = self.arb.waiting(1, cam)
        if any(r["rule"] == rule for r in queued) or now - self.last_p1.get(cam, 0) < 1.0:
            return                                              # dedupe; < 1 s since this camera's last P1
        if len(queued) >= 3:
            self.arb.drop(min(queued, key=lambda r: r["created"]))
        self.last_p1[cam] = now
        self.n_triggers += 1
        self.arb.submit({"prio": 1, "cam": cam, "rule": rule, "trigger": "gate:" + rule, "created": time.time(),
                         "frames": pick_frames(det.buffer), "evidence": self.evidence(det, now),
                         "hint": tr["hint"], "track_ids": tr["track_ids"], "kind": tr.get("kind")})

    def baseline(self, det, now):
        cam = det.cam.id
        if self.arb.waiting(1) or self.arb.waiting(3, cam):
            return                                              # no P1 waiting anywhere; ≤ 1 pending baseline per camera
        anyone = any(persons(e) for e in det.buffer)
        interval = V["baseline_interval_s"] if anyone else V["empty_interval_s"]
        last = self.last_call.get(cam)
        if last and now - last[0] < interval:
            return
        if last and not self.events.has_open(cam) and now - last[0] < V["baseline_skip"]["max_skip_s"]:
            new = det.buffer[-1]
            if {t["id"] for t in persons(new)} == last[2] and mad(grey160(new[1]), last[1]) < V["baseline_skip"]["mad"]:
                if now - self.last_skip.get(cam, 0) >= interval:   # one skip counted per baseline slot
                    self.skipped += 1
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
        self.last_call[cam] = (entry[0], grey160(entry[1]), {t["id"] for t in persons(entry)})


if __name__ == "__main__":
    import numpy as np
    from types import SimpleNamespace as NS

    class FakeArb:
        def __init__(self): self.q = []
        def submit(self, r): self.q.append(r); return r
        def waiting(self, prio=None, cam=None): return [r for r in self.q if (prio is None or r["prio"] == prio) and (cam is None or r["cam"] == cam)]
        def drop(self, r): self.q.remove(r)
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
    for i in range(1, 100):
        step(i / 10)
    assert arb.q == [] and s.skipped == 3, (arb.q, s.skipped)
    # ...but never longer than 15 s.
    for i in range(100, 151):
        step(i / 10)
    assert [r["trigger"] for r in arb.q] == ["baseline"], arb.q
    arb.q.clear(); s.note_call("cam1", det.buffer[-1])
    # A new person appearing ends the skip at the next 3 s slot.
    for i in range(151, 181):
        step(i / 10, tracks=(walker, {"id": 2, "cls": "person", "box": (300, 100, 350, 300)}))
    assert [r["trigger"] for r in arb.q] == ["baseline"], arb.q
    arb.q.clear()
    # A fall: the person_down gate fires -> P1 with frozen frames; repeat triggers are deduped while it waits.
    det.person_hists = lambda: {1: [(0.1 * i, 100, 100 + (i >= 8) * 100, 200, 300) for i in range(11)]}
    step(18.1); step(18.2)
    p1 = arb.waiting(1)
    assert len(p1) == 1 and p1[0]["trigger"] == "gate:person_down" and len(p1[0]["frames"]) == 4, p1
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
    det.person_hists = lambda: sofa(31 + G["horizontal_recheck_s"]); step(32.0 + G["horizontal_recheck_s"])
    assert arb.waiting(1), "re-armed after horizontal_recheck_s"
    arb.q.clear(); s.silence("cam1", [3], 70.0)
    det.person_hists = lambda: {3: [(70.1, 150, 100, 200, 320)]}; step(70.1)   # stood up: re-armed
    assert ("cam1", 3) not in s.quiet
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
