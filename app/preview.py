"""P1 validation tool: live grid of every configured camera with YOLO boxes, track IDs and stats.

  uv run python -m app.preview          # press q in the window to quit
The real dashboard comes in P3; this window exists so cameras and tracking can be validated now.
"""
import math
import time

import cv2
import numpy as np

from app.detect import Detector
from app.ingest import CameraManager

TILE_W, TILE_H = 640, 360


def tile(det):
    img = cv2.imdecode(np.frombuffer(det.jpeg, np.uint8), cv2.IMREAD_COLOR) if det.jpeg else np.zeros((TILE_H, TILE_W, 3), np.uint8)
    img = cv2.resize(img, (TILE_W, TILE_H))
    s, c = det.stats(), det.cam
    line = f"{c.id} {c.name} | {c.status} | cap {c.fps():.0f} fps | yolo {s['yolo_ms_p50']} ms | keep-up {s['keep_up']} | tracks {s['tracks']}"
    cv2.rectangle(img, (0, 0), (TILE_W, 22), (0, 0, 0), -1)
    cv2.putText(img, line, (6, 15), 0, 0.45, (255, 255, 255), 1)
    return img


if __name__ == "__main__":
    mgr = CameraManager()
    dets = [Detector(c) for c in mgr.cams.values()]
    for d in dets:
        d.start()
    cols = math.ceil(math.sqrt(len(dets)))
    while True:
        tiles = [tile(d) for d in dets]
        tiles += [np.zeros_like(tiles[0])] * (cols * math.ceil(len(tiles) / cols) - len(tiles))
        rows = [np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)]
        cv2.imshow("HackHive preview (q to quit)", np.vstack(rows))
        if cv2.waitKey(50) & 0xFF == ord("q"):
            break
    for d in dets:
        d.stop()
    print({d.cam.id: d.stats() for d in dets})
