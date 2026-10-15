"""List camera indices with their names, or test a stream URL (SPEC E-12, E-15).

  uv run python scripts/list_cameras.py                     # webcams / Continuity Camera: index -> name -> resolution
  uv run python scripts/list_cameras.py --url http://IP:8080/video   # check a phone IP-camera stream
"""
import re
import subprocess
import sys
import time

import cv2


def names():
    """{OpenCV index: name}. OpenCV can't name devices, so ffmpeg's AVFoundation listing names them, but OpenCV's list
    leaves out Desk View cameras and screens (measured: ffmpeg [1] Desk View -> OpenCV "out of bound (0-0)"), so the
    index is the position among the rest. ponytail: assumes both lists keep the same order; check with an iPhone."""
    out = subprocess.run(["ffmpeg", "-hide_banner", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
                         capture_output=True, text=True).stderr
    video = out.split("audio devices")[0]
    found = [n for _, n in re.findall(r"\[(\d+)\] (.+)", video) if "Desk View" not in n and "Capture screen" not in n]
    return dict(enumerate(found))


def probe(src, label):
    cap = cv2.VideoCapture(src, cv2.CAP_AVFOUNDATION if isinstance(src, int) else cv2.CAP_FFMPEG)
    t = time.time(); ok, frame = cap.read()
    while not ok and time.time() - t < 5:
        ok, frame = cap.read()
    if ok:
        print(f"  ✅ {label}: {frame.shape[1]}x{frame.shape[0]}")
    else:
        print(f"  ❌ {label}: no frames (permission, cable, or network?)")
    cap.release()
    return ok


if __name__ == "__main__":
    if "--url" in sys.argv:
        url = sys.argv[sys.argv.index("--url") + 1]
        sys.exit(0 if probe(url, url) else 1)
    found = names()
    print("Video devices (use the number as `source:` in config.yaml):")
    for i, n in found.items():
        probe(i, f"[{i}] {n}")
