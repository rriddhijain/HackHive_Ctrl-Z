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
    """{OpenCV index: name}. Uses ffmpeg if present, otherwise system_profiler SPCameraDataType. OpenCV leaves out
    Desk View cameras and screens, so the index is the position among the rest. Never opens a camera: the server
    calls this on every device listing. ponytail: assumes both lists keep OpenCV's order; check with an iPhone."""
    try:
        out = subprocess.run(["ffmpeg", "-hide_banner", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
                             capture_output=True, text=True).stderr
        video = out.split("audio devices")[0]
        found = [n for _, n in re.findall(r"\[(\d+)\] (.+)", video) if "Desk View" not in n and "Capture screen" not in n]
        if found:
            return dict(enumerate(found))
    except FileNotFoundError:
        pass

    try:
        sp = subprocess.run(["system_profiler", "SPCameraDataType"], capture_output=True, text=True).stdout
        cams = [line.strip().rstrip(':') for line in sp.splitlines() if line.startswith('    ') and not line.startswith('      ') and line.strip()]
        filtered = [n for n in cams if "Desk View" not in n and "Capture screen" not in n]
        if filtered:
            return dict(enumerate(filtered))
    except Exception:
        pass
    return {}


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
