"""Capture: one thread per camera that keeps ONLY the latest frame (SPEC §5a.1 step 1, FR-1–FR-3, E-13).

Sources: int -> webcam index (AVFoundation), file path -> played at native FPS against the wall clock,
http(s)/rtsp URL -> network stream with reconnect backoff.
"""
import threading
import time
from collections import deque
from pathlib import Path

import cv2

from app.config import CFG, ROOT

BACKOFF = (1, 2, 4, 5)


def source_type(src):
    if isinstance(src, int):
        return "webcam"
    return "stream" if str(src).startswith(("http://", "https://", "rtsp://")) else "file"


class Camera(threading.Thread):
    def __init__(self, cam_id, name, source, loop=True, door_zone=None, watch_zone=None):
        super().__init__(daemon=True, name=f"cap-{cam_id}")
        self.id, self.name, self.source, self.loop = cam_id, name, source, loop
        self.door_zone, self.watch_zone = door_zone, watch_zone
        self.kind = source_type(source)
        self.status = "starting"       # live | reconnecting | down | ended | stopped
        self.reconnects = 0
        self._latest = None            # (frame, t_capture, idx)
        self.t_first = None            # wall time of the first frame = clip time 0 (onset-to-alert on replays, §12)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._ts = deque(maxlen=60)    # capture timestamps, for fps

    def _open(self):
        if self.kind == "webcam":
            return cv2.VideoCapture(self.source, cv2.CAP_AVFOUNDATION)
        if self.kind == "file":
            path = Path(self.source)
            return cv2.VideoCapture(str(path if path.is_absolute() else ROOT / path))
        return cv2.VideoCapture(self.source, cv2.CAP_FFMPEG)

    def run(self):
        idx, attempt = 0, 0
        while not self._stop.is_set():
            cap = self._open()
            if not cap.isOpened():
                self.status = "reconnecting" if self.kind != "file" else "down"
                if self.kind == "file":
                    return
                time.sleep(BACKOFF[min(attempt, len(BACKOFF) - 1)]); attempt += 1; self.reconnects += 1
                continue
            attempt, self.status = 0, "live"
            frame_dt = 1.0 / (cap.get(cv2.CAP_PROP_FPS) or 25) if self.kind == "file" else 0
            next_t = time.time()
            while not self._stop.is_set():
                ok, frame = cap.read()
                if not ok:
                    break
                if frame_dt:  # pace files to real time
                    next_t += frame_dt
                    delay = next_t - time.time()
                    if delay > 0:
                        time.sleep(delay)
                    elif delay < -1:  # fell far behind (e.g. laptop slept): resync, don't fast-forward
                        next_t = time.time()
                t = time.time(); idx += 1
                self.t_first = self.t_first or t
                with self._lock:
                    self._latest = (frame, t, idx)
                self._ts.append(t)
            cap.release()
            if self._stop.is_set():
                break
            if self.kind == "file":
                if not self.loop:
                    self.status = "ended"; return
                continue  # loop the file
            self.status = "reconnecting"; self.reconnects += 1
            time.sleep(BACKOFF[0])
        self.status = "stopped"

    def latest(self):
        with self._lock:
            return self._latest

    def fps(self):
        ts = list(self._ts)
        return (len(ts) - 1) / (ts[-1] - ts[0]) if len(ts) > 1 and ts[-1] > ts[0] else 0.0

    def stop(self):
        self._stop.set()


class CameraManager:
    def __init__(self, cameras=None):
        self.cams = {}
        for c in cameras if cameras is not None else CFG["cameras"]:
            self.add(c["id"], c["name"], c["source"], door_zone=c.get("door_zone"), watch_zone=c.get("watch_zone"))

    def add(self, cam_id, name, source, loop=True, door_zone=None, watch_zone=None):
        cam = Camera(cam_id, name, source, loop, door_zone, watch_zone)
        self.cams[cam_id] = cam
        cam.start()
        return cam

    def remove(self, cam_id):
        cam = self.cams.pop(cam_id, None)
        if cam:
            cam.stop()

    def next_id(self):
        n = 1
        while f"cam{n}" in self.cams:
            n += 1
        return f"cam{n}"

    def stats(self):
        return {cid: {"name": c.name, "source_type": c.kind, "status": c.status,
                      "capture_fps": round(c.fps(), 1), "reconnects": c.reconnects} for cid, c in self.cams.items()}


if __name__ == "__main__":
    # Self-check: play the sample file for 3 s; it must run at ~native FPS and deliver fresh frames.
    clip = "data/demo/sample_bus.mp4"
    m = CameraManager([{"id": "t1", "name": "test", "source": clip}])
    time.sleep(3)
    s = m.stats()["t1"]; f = m.cams["t1"].latest()
    print(s)
    assert s["status"] == "live" and 20 <= s["capture_fps"] <= 30, s
    assert f is not None and time.time() - f[1] < 0.2, "latest frame is stale"
    assert m.next_id() == "cam1"
    m.remove("t1")
    print("ingest self-check ok")
