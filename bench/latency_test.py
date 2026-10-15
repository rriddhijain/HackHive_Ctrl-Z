"""P0 model lock: latency + contention test for the candidate VLMs on this machine.

Measures, per model, for a realistic request (2x2 mosaic of 336 px tiles + hints, streamed JSON):
  ttft      time to first token
  t_cat     time until "category" and "confidence" have streamed (= time-to-alert part spent in the model)
  total     time until the full JSON is done
plus JSON validity, and a contention run (2 incident calls + 1 chat call fired at once).

Usage: uv run python -m bench.latency_test [model ...]
"""
import base64, json, os, statistics, sys, threading, time

import cv2, httpx, numpy as np, ultralytics

OLLAMA = "http://localhost:11434/api/chat"
CATEGORIES = ["fire_smoke", "fighting", "person_down", "crowd_incident", "property_damage",
              "suspicious_activity", "tailgating", "normal"]
SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": CATEGORIES},
        "confidence": {"type": "number"},
        "subtype": {"type": ["string", "null"]},
        "people_count": {"type": "integer"},
        "summary": {"type": "string"},
    },
    "required": ["category", "confidence", "subtype", "people_count", "summary"],
}
SYSTEM = ("You are a CCTV incident classifier. The image is a 2x2 grid of 4 frames in time order "
          "(left to right, top to bottom) spanning about 2 seconds. Categories: " + ", ".join(CATEGORIES) +
          ". Pick the single most severe category clearly visible; if unsure choose normal. "
          "Summary: objective, at most 30 words. Reply only with JSON.")


_D = os.path.join(os.path.dirname(ultralytics.__file__), "assets")
_SRC = [cv2.imread(os.path.join(_D, f)) for f in ("bus.jpg", "zidane.jpg", "bus.jpg", "zidane.jpg")]
_rng = np.random.default_rng(0)


def mosaic_b64(tile=int(os.environ.get('TILE', 336))):
    # a fresh random crop + brightness per tile, so the runtime can't reuse a cached image (live cameras never repeat)
    tiles = []
    for i in _SRC:
        h, w = i.shape[:2]; y, x = _rng.integers(0, h // 5), _rng.integers(0, w // 5)
        t = cv2.resize(i[y:y + h * 4 // 5, x:x + w * 4 // 5], (tile, tile))
        tiles.append(cv2.convertScaleAbs(t, alpha=1, beta=int(_rng.integers(-25, 25))))
    grid = np.vstack([np.hstack(tiles[:2]), np.hstack(tiles[2:])])
    return base64.b64encode(cv2.imencode(".jpg", grid, [cv2.IMWRITE_JPEG_QUALITY, 80])[1]).decode()


def call(model, image=True, max_tokens=100):
    msg = {"role": "user", "content": "Detector hints: persons=4, no gate triggers. Classify."}
    if image:
        msg["images"] = [mosaic_b64()]
    body = {"model": model, "stream": True, "think": False, "keep_alive": -1,
            "format": SCHEMA if image else None,
            "options": {"temperature": 0, "num_predict": max_tokens},
            "messages": [{"role": "system", "content": SYSTEM}, msg] if image else [msg]}
    t0 = time.perf_counter(); ttft = t_cat = None; text = ""
    with httpx.stream("POST", OLLAMA, json=body, timeout=60) as r:
        for line in r.iter_lines():
            if not line:
                continue
            chunk = json.loads(line)
            piece = chunk.get("message", {}).get("content", "")
            if piece and ttft is None:
                ttft = time.perf_counter() - t0
            text += piece
            if t_cat is None and '"confidence"' in text and any(c in text[text.index('"confidence"') + 13:] for c in ",}\n"):
                t_cat = time.perf_counter() - t0
            if chunk.get("done"):
                break
    total = time.perf_counter() - t0
    try:
        json.loads(text); valid = True
    except ValueError:
        valid = False
    return {"ttft": ttft, "t_cat": t_cat or total, "total": total, "valid": valid, "text": text}


def pct(xs, q):
    xs = sorted(xs); return xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))]


def bench(model, n=8):
    call(model)  # warm-up / load
    runs = [call(model) for _ in range(n)]
    out = {"model": model, "valid": sum(r["valid"] for r in runs) / n}
    for k in ("ttft", "t_cat", "total"):
        xs = [r[k] for r in runs if r[k] is not None]
        out[k] = {"p50": round(statistics.median(xs), 3), "p95": round(pct(xs, 0.95), 3)}
    out["sample"] = runs[-1]["text"][:200]
    return out


def contention(model):
    res = {}
    def run(name, image):
        res[name] = call(model, image=image, max_tokens=100 if image else 60)
    ts = [threading.Thread(target=run, args=a) for a in (("cam1", True), ("cam2", True), ("chat", False))]
    t0 = time.perf_counter()
    for t in ts: t.start()
    for t in ts: t.join()
    return {k: {"t_cat": round(v["t_cat"], 3), "total": round(v["total"], 3)} for k, v in res.items()} | \
           {"wall": round(time.perf_counter() - t0, 3)}


if __name__ == "__main__":
    models = sys.argv[1:] or ["qwen3.5:4b", "qwen3.5:4b-mlx", "qwen3.5:2b"]
    results = []
    for m in models:
        r = bench(m); r["contention"] = contention(m); results.append(r)
        print(json.dumps(r, indent=1), flush=True)
        httpx.post(OLLAMA, json={"model": m, "keep_alive": 0, "messages": []}, timeout=30)  # unload before next model
    os.makedirs("bench/results", exist_ok=True)
    json.dump(results, open(f"bench/results/latency_p0_tile{os.environ.get('TILE', 336)}.json", "w"), indent=1)
