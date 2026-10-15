"""Detect: one thread per camera running YOLO + ByteTrack at ~10 FPS (SPEC §5a.1 step 2, FR-6).

Each detector has ITS OWN YOLO instance: model.track(persist=True) keeps tracker state on the model,
so sharing one instance across cameras would mix their track IDs.
Produces, per camera: a ring buffer of the last few seconds (t_capture, frame, tracks), per-track features
for the gate rules, and a pre-encoded annotated JPEG for the live view.

Coordinates: every box, track history and zone in this module is in PIXELS of the resized frame
(frame_width wide, source aspect kept), the same system gate.py uses. Normalising x and y separately
would scale width/height ratios by the frame's aspect (0.56 on 16:9) and break the gates.
Zones are normalised only in config.yaml (SPEC §10) and converted to pixels once per frame size.
"""
import threading
import time
from collections import deque

import cv2
import numpy as np
from ultralytics import YOLO

from app.config import CFG, ROOT

DET = CFG["detector"]
NAMES = {0: "person", 24: "backpack", 26: "handbag", 28: "suitcase", 43: "knife"}
GREEN, AMBER, BLUE = (80, 200, 80), (0, 190, 255), (255, 160, 60)
# Metal (mps) is not thread-safe: concurrent YOLO calls from several camera threads abort the process
# ("failed assertion _status < MTLCommandBufferStatusCommitted"). On mps, calls take turns. CPU needs no lock.
GPU_LOCK = threading.Lock()


def in_poly(pt, poly):
    """Point-in-polygon (ray casting); pt and poly in the same coordinate system."""
    x, y = pt; inside = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1:
            inside = not inside
    return inside


class Track:
    """History + features for one tracked object (used by the gate rules in P2)."""

    def __init__(self, tid, cls, t):
        self.id, self.cls, self.first_seen, self.last_seen = tid, cls, t, t
        self.hist = deque(maxlen=60)          # (t, x1, y1, x2, y2) in frame pixels, ~6 s at 10 FPS
        self.zone_entries = {}                # zone name -> times this track entered it
        self._in_zone = {}

    def update(self, t, box, zones):
        self.last_seen = t
        self.hist.append((t, *box))
        foot = ((box[0] + box[2]) / 2, box[3])  # bottom-centre = where the person stands
        for name, poly in zones.items():
            now_in = in_poly(foot, poly)
            if now_in and not self._in_zone.get(name):
                self.zone_entries.setdefault(name, []).append(t)
            self._in_zone[name] = now_in

    def dwell(self):
        return self.last_seen - self.first_seen


class Detector(threading.Thread):
    def __init__(self, camera, on_frame=None):
        super().__init__(daemon=True, name=f"det-{camera.id}")
        self.cam, self.on_frame = camera, on_frame   # on_frame(detector) is called after every processed frame (gate hook)
        self.model = YOLO(str(ROOT / DET["model"]))
        self.model.predict(np.zeros((360, 640, 3), np.uint8), device=DET["device"], verbose=False)  # warm-up: first call is slow
        self.buffer = deque(maxlen=int(DET["buffer_s"] * DET["fps"]))  # (t_capture, frame, tracks)
        self.tracks = {}
        self.jpeg = None                 # latest annotated frame, JPEG bytes
        self.yolo_ms = deque(maxlen=100)
        self.sampled = self.processed = self.errors = 0
        self._last_idx, self._stop = -1, threading.Event()
        zones = {"door": camera.door_zone, "watch": camera.watch_zone}
        self.zones_norm = {k: v for k, v in zones.items() if v}   # as in config.yaml
        self.zones, self._zone_size = {}, None                       # same zones in frame pixels

    def _zones_px(self, sw, sh):
        if self._zone_size != (sw, sh):  # once per frame size (a source could change resolution on reconnect)
            self.zones = {k: [(x * sw, y * sh) for x, y in p] for k, p in self.zones_norm.items()}
            self._zone_size = (sw, sh)
        return self.zones

    def run(self):
        period, next_t = 1.0 / DET["fps"], time.time()
        while not self._stop.is_set():
            next_t += period
            late = time.time() - next_t
            if late > period:            # missed ticks = frames sampled but not processed (keep-up < 100 %)
                missed = int(late / period); self.sampled += missed; next_t += missed * period
            got = self.cam.latest()
            if got and got[2] != self._last_idx:
                self.sampled += 1
                try:
                    self._process(*got)
                    if self.on_frame:
                        self.on_frame(self)
                except Exception as e:  # never let one bad frame kill the camera's detector (E-5 spirit)
                    self._last_idx = got[2]; self.errors += 1
                    if self.errors <= 3:
                        print(f"[det-{self.cam.id}] frame error: {e!r}", flush=True)
            delay = next_t - time.time()
            if delay > 0:
                time.sleep(delay)

    def _process(self, frame, t_capture, idx):
        self._last_idx = idx
        h, w = frame.shape[:2]
        fw = DET["frame_width"]
        small = cv2.resize(frame, (fw, int(h * fw / w))) if w != fw else frame
        t0 = time.perf_counter()
        kw = dict(persist=True, tracker="bytetrack.yaml", classes=DET["classes"], conf=DET["conf"],
                  imgsz=DET["imgsz"], device=DET["device"], verbose=False)
        if DET["device"] == "mps":
            with GPU_LOCK:
                r = self.model.track(small, **kw)[0]
        else:
            r = self.model.track(small, **kw)[0]
        self.yolo_ms.append((time.perf_counter() - t0) * 1000)
        self.processed += 1
        sh, sw = small.shape[:2]
        zones = self._zones_px(sw, sh)
        tracks = []
        if r.boxes is not None and r.boxes.id is not None:
            # r.boxes.xyxy is already in pixels of `small` (Ultralytics maps its letterboxed input back)
            for box, tid, cls, conf in zip(r.boxes.xyxy.tolist(), r.boxes.id.int().tolist(),
                                           r.boxes.cls.int().tolist(), r.boxes.conf.tolist()):
                box = tuple(box)
                tr = self.tracks.get(tid) or self.tracks.setdefault(tid, Track(tid, cls, t_capture))
                tr.update(t_capture, box, zones)
                tracks.append({"id": tid, "cls": NAMES.get(cls, str(cls)), "box": box, "conf": round(conf, 2)})
        for tid in [k for k, v in self.tracks.items() if t_capture - v.last_seen > 5]:
            del self.tracks[tid]  # forget tracks unseen for 5 s
        self.buffer.append((t_capture, small, tracks))
        self.jpeg = cv2.imencode(".jpg", self._annotate(small.copy(), tracks), [cv2.IMWRITE_JPEG_QUALITY, 70])[1].tobytes()

    def person_hists(self):
        """{track_id: history} of PERSON tracks only: the one input the gate rules take (SPEC §6.6).
        Bags and knives are tracked for hints and the live view but never gated: a backpack's box overlaps its
        wearer and its small height turns walking into a 'fighting' speed; a suitcase on the floor looks 'horizontal'."""
        return {tid: list(tr.hist) for tid, tr in self.tracks.items() if tr.cls == 0}

    def _annotate(self, img, tracks):
        for name, poly in self.zones.items():
            pts = np.array(poly, np.int32)
            cv2.polylines(img, [pts], True, BLUE, 2); cv2.putText(img, name, tuple(int(v) for v in pts[0]), 0, 0.5, BLUE, 1)
        for t in tracks:
            x1, y1, x2, y2 = (int(v) for v in t["box"])
            col = GREEN if t["cls"] == "person" else AMBER
            cv2.rectangle(img, (x1, y1), (x2, y2), col, 2)
            cv2.putText(img, f'{t["cls"]} #{t["id"]}', (x1, max(12, y1 - 4)), 0, 0.45, col, 1)
        return img

    def stats(self):
        ms = sorted(self.yolo_ms)
        return {"det_fps": round(self.processed and min(DET["fps"], len(ms) and 1000 / max(np.mean(ms), 1)), 1),
                "yolo_ms_p50": round(ms[len(ms) // 2], 1) if ms else None,
                "yolo_ms_p95": round(ms[int(len(ms) * 0.95) - 1], 1) if len(ms) > 20 else None,
                "keep_up": round(self.processed / self.sampled, 3) if self.sampled else None,
                "tracks": len(self.tracks)}

    def stop(self):
        self._stop.set()


if __name__ == "__main__":
    # Self-check: run on the sample clip for 6 s -> people detected, stable IDs, keep-up 100 %, YOLO fast enough.
    from app.ingest import CameraManager
    assert in_poly((0.5, 0.5), [[0, 0], [1, 0], [1, 1], [0, 1]]) and not in_poly((1.5, 0.5), [[0, 0], [1, 0], [1, 1], [0, 1]])
    m = CameraManager([{"id": "t1", "name": "test", "source": "data/demo/sample_bus.mp4",
                        "door_zone": [[0, 0.5], [0.5, 0.5], [0.5, 1], [0, 1]]}])
    d = Detector(m.cams["t1"]); d.start()
    time.sleep(6)
    s = d.stats(); print(s, "buffer", len(d.buffer))
    persons = [t for t in d.buffer[-1][2] if t["cls"] == "person"]
    print("persons in last frame:", [(t["id"], t["conf"]) for t in persons])
    assert persons, "no person detected in bus.jpg clip"
    assert s["keep_up"] is not None and s["keep_up"] >= 0.95, s
    assert s["yolo_ms_p50"] < 60, s
    assert d.jpeg and d.jpeg[:2] == b"\xff\xd8"
    _, frame, last = d.buffer[-1]
    fh, fw = frame.shape[:2]
    assert fw == DET["frame_width"] and all(0 <= t["box"][0] < t["box"][2] <= fw + 1 and 0 <= t["box"][1] < t["box"][3] <= fh + 1
                                           for t in last), "boxes must be in frame pixels"
    assert d.zones["door"][2] == (0.5 * fw, fh), d.zones  # config's normalised zone, now in the same pixels
    from app.gate import norm_speed, person_down, DEFAULTS
    hists = d.person_hists()
    assert set(hists) == {tid for tid, tr in d.tracks.items() if tr.cls == 0}, "gates must only see person tracks"
    # A 150x60 px lying box held for 1 s is 'horizontal' (2.5 wide per tall). With per-axis normalised coordinates
    # on this 16:9 frame it would read 1.4 and only just pass; a 1.5-ratio body would read 0.84 and be missed.
    lying = [(i / 10, 100, 300, 250, 360) for i in range(11)]
    assert person_down(lying, DEFAULTS), "horizontal rule must fire on true pixel shapes"
    tid = persons[0]["id"]; print("track feats: speed %.2f body heights/s, dwell %.1fs" % (norm_speed(hists[tid]), d.tracks[tid].dwell()))
    d.stop(); m.remove("t1")
    print("detect self-check ok")
