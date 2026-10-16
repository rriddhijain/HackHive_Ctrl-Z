"""VLM call: letterboxed mosaic, prompt, streaming client, category probabilities, cross-check (SPEC §5a steps 5–7, §6.5, §7.3, E-7).

Category probabilities (§6.5, D60): the model writes the category value token by token, and with the JSON schema it
usually starts with ONE character ("c", "f", "p"...), which is shared by two names (fire_smoke/fighting,
person_down/property_damage). So we walk the value's tokens until the chosen name is unique (1–2 tokens, ~35 ms each):
the chosen branch is exact; the mass of an un-taken alternative is split evenly over the names it can still become.
"""
import base64
import json
import math
import re
import time

import cv2
import httpx
import numpy as np

from app.config import CFG

V = CFG["vlm"]
# §6.1: name, definition, "not this", subtypes, severity. Order = §6.2 tie-break (most severe first).
TABLE = [
    ("fire_smoke", "Visible flames or smoke", "NOT red/orange lights, sunsets, reflections, steam from cooking or a kettle",
     ["fire", "smoke"], "critical"),
    ("fighting", "2+ people in physical aggression: punching, kicking, shoving, wrestling",
     "NOT hugging, handshakes, high-fives, sports, dancing, people simply standing close", [], "critical"),
    ("person_down", "A person lying or collapsed on the floor (fall, fainting)",
     "NOT sitting on the floor or a chair, kneeling, bending to pick something up, lying on a bed/sofa/bench", [], "critical"),
    ("crowd_incident", "Abnormally dense gathering, or a crowd suddenly running/dispersing",
     "NOT a normal queue, a seated audience, people walking through a busy area at normal pace", ["gathering", "running"], "high"),
    ("property_damage", "Damage to property or a hazardous object event, accidental or deliberate: an object/debris falling, "
     "a structure collapsing, items knocked over and broken, shattered glass, vandalism",
     "NOT someone carefully carrying, moving or placing objects; NOT already-broken items with nothing happening",
     ["falling_object", "collapse", "breakage", "vandalism"], "high"),
    ("suspicious_activity", "Loitering, trespassing/climbing, theft/shoplifting, an abandoned object, a visible weapon",
     "NOT people standing, waiting, talking or using a phone; NOT carrying bags normally; NOT tools used for work",
     ["weapon", "theft", "trespass", "loitering", "abandoned_object", "other"], "by_subtype"),
    ("tailgating", "A second person follows closely on foot through a door/gate on one opening",
     "NOT vehicles; NOT people near a car or bus; NOT anyone who is not passing through a door or gate", [], "medium"),
    ("normal", "None of the above", None, [], "none"),
]
CATS = [r[0] for r in TABLE]
SUBTYPES = {r[0]: r[3] for r in TABLE}
GATE_CAT = {"person_down": "person_down", "fighting": "fighting", "tailgating": "tailgating"}  # gate rule -> category it supports


def severity(cat, subtype):
    sev = dict((r[0], r[4]) for r in TABLE)[cat]
    if sev == "by_subtype":  # D35
        return "medium" if subtype in ("loitering", "abandoned_object") else "critical"
    return sev


SCHEMA = {  # §7.3, fields in this order; flat subtype enum (D49)
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": CATS},
        "subtype": {"type": ["string", "null"], "enum": sorted({s for r in TABLE for s in r[3]}) + [None]},
        "people_count": {"type": "integer"},
        "summary": {"type": "string"},
    },
    "required": ["category", "subtype", "people_count", "summary"],
}

SYSTEM = (  # all static text (prefix-cached, D38); every §6.1 definition + exclusion verbatim (D49)
    "You watch one CCTV camera. The image is a 2x2 grid of 4 frames in time order (top-left, top-right, bottom-left, "
    "bottom-right) spanning about 2 seconds; grey bars are padding. Classify what is happening into exactly one category. "
    "If several apply, pick the most severe, in this order: " + " > ".join(CATS) + ". If unsure, choose normal.\n\n"
    "Categories:\n" + "\n".join(
        f"- {n}: {d}." + (f" {x}." if x else "") + (f" Subtypes: {', '.join(s)}." if s else "") for n, d, x, s, _ in TABLE) +
    "\n\nThe text sent with the image is metadata from the detector (people counts, box motion, scene change), not a "
    "description of the scene. Use it only as a hint; never mention it or the detector in the summary, which describes "
    "only what the frames show."
    "\n\nFields: category; subtype (one of that category's subtypes, else null); people_count (people visible in the "
    "newest frame); summary (objective, at most 30 words: who, what, where in the frame). Reply only with JSON."
)


def user_turn(max_persons, hint=None, crop=False):
    """The dynamic user turn (D77): labelled as detector metadata so the model never narrates it as scene content.
    hint: gate text (§7.4) with numbers and a named hypothesis, no track ids, never the word gate; crop: FR-9c tile."""
    s = f"Detector metadata, not visible in the frames: up to {max_persons} people in the last 4 s; trigger: {hint or 'none'}."
    return s + (" The bottom-right tile is a close-up of the people in the trigger, newest frame." if crop else "")


# ---- mosaic (§5a step 5, D44) ----
def letterbox(img, tw, th):
    """Fit img into tw x th without stretching or cropping; grey padding."""
    h, w = img.shape[:2]
    s = min(tw / w, th / h)
    nw, nh = max(1, round(w * s)), max(1, round(h * s))
    out = np.full((th, tw, 3), 114, np.uint8)
    x, y = (tw - nw) // 2, (th - nh) // 2
    out[y:y + nh, x:x + nw] = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)
    return out


def pick_frames(buffer, span=V["mosaic_span_s"], n=V["mosaic_frames"]):
    """Buffer entries nearest to newest - span ... newest (offsets -2.0, -1.33, -0.67, 0 s); fewer if the buffer is short."""
    buf = list(buffer)
    if not buf:
        return []
    t_new = buf[-1][0]
    picked = []
    for k in range(n):
        target = t_new - span * (n - 1 - k) / (n - 1)
        e = min(buf, key=lambda b: abs(b[0] - target))
        if not picked or e is not picked[-1]:
            picked.append(e)
    return picked


def track_crop(entry, track_ids, C=V["p1_crop"]):
    """FR-9c (D45): 16:9 crop of the trigger tracks' union box x expand from a buffer entry, or None if the box is
    already >= max_box_frac of the frame height (close enough to see) or the tracks aren't in this frame."""
    img, boxes = entry[1], [t["box"] for t in entry[2] if t["id"] in track_ids]
    if not boxes:
        return None
    H, W = img.shape[:2]
    x1, y1 = min(b[0] for b in boxes), min(b[1] for b in boxes)
    x2, y2 = max(b[2] for b in boxes), max(b[3] for b in boxes)
    if y2 - y1 >= C["max_box_frac"] * H:
        return None
    w = max(x2 - x1, (y2 - y1) * 16 / 9) * C["expand"]
    w, h = min(w, W, H * 16 / 9), min(w, W, H * 16 / 9) * 9 / 16
    cx = min(max((x1 + x2) / 2, w / 2), W - w / 2)
    cy = min(max((y1 + y2) / 2, h / 2), H - h / 2)
    return img[int(cy - h / 2):int(cy + h / 2), int(cx - w / 2):int(cx + w / 2)]


def mosaic(frames, track_ids=()):
    """2x2 grid of letterboxed 288x160 tiles (576x320) from buffer entries (t, frame, tracks). Returns (image, b64 jpeg).
    track_ids (gate-triggered calls) + vlm.p1_crop.enabled: tile 4 becomes a crop of those tracks (FR-9c)."""
    tw, th = V["tile"]
    tiles = [letterbox(f[1], tw, th) for f in frames]
    crop = track_crop(frames[-1], track_ids) if V["p1_crop"]["enabled"] and track_ids and frames else None
    if crop is not None:
        tiles[-1] = letterbox(crop, tw, th)
    tiles += [np.full((th, tw, 3), 114, np.uint8)] * (4 - len(tiles))
    grid = np.vstack([np.hstack(tiles[:2]), np.hstack(tiles[2:4])])
    return grid, base64.b64encode(cv2.imencode(".jpg", grid, [cv2.IMWRITE_JPEG_QUALITY, 85])[1]).decode()


# ---- category probabilities (§6.5, D60) ----
_VALUE = re.compile(r'"category"\s*:\s*"')


def _cats_for(text):
    """Categories the category value in `text` can still become, or None if text isn't inside the value yet."""
    m = _VALUE.search(text)
    if not m:
        return None
    v = text[m.end():]
    if '"' in v:
        v = v[:v.index('"')]
        return [v] if v in CATS else []
    return [c for c in CATS if c.startswith(v)]


def walk(steps):
    """steps: [(text_before_token, chosen_token, [(alt_token, logprob), ...])] for the tokens of the category value.
    Returns (probs over all 8 categories, summing to 1, or None if not resolved yet; chosen category)."""
    mass, branch = dict.fromkeys(CATS, 0.0), 1.0
    for before, chosen, alts in steps:
        opts = [(t, _cats_for(before + t), math.exp(lp)) for t, lp in alts]
        opts = [(t, cs, p) for t, cs, p in opts if cs]          # legal value tokens only, renormalised
        chosen_cats = _cats_for(before + chosen)
        z = sum(p for *_, p in opts) or 1.0
        p_chosen = 0.0
        for t, cs, p in opts:
            if t == chosen:
                p_chosen += p / z
            else:
                for c in cs:
                    mass[c] += branch * p / z / len(cs)
        branch *= p_chosen or 1.0
        if chosen_cats and len(chosen_cats) == 1:
            mass[chosen_cats[0]] += branch
            s = sum(mass.values())
            return {c: v / s for c, v in mass.items()}, chosen_cats[0]
    return None, None


def calibrate(probs, T=CFG["events"]["calibration_T"]):
    """p_cal = softmax(log p / T) (§6.5)."""
    e = {c: math.exp(math.log(max(p, 1e-9)) / T) for c, p in probs.items()}
    s = sum(e.values())
    return {c: v / s for c, v in e.items()}


# ---- cross-check (E-7, D46) ----
def cross_check(p, evidence, E=CFG["events"]):
    """c = clamp(p_cal * f): f = 1.15 if a gate trigger supports the category, 0.5 if the detector contradicts it.
    evidence: {"max_persons": int over the 4 s buffer, "door": bool, "door_entries": int, "triggers": set of categories}.
    Returns (c, vetoes) where vetoes = [(category, p_before, p_after)]."""
    contra = {"fighting": evidence["max_persons"] < 1,   # nano misses grapplers: veto only if nobody seen (D63)
              "person_down": evidence["max_persons"] < 1,
              "tailgating": not evidence["door"] or evidence["door_entries"] < 2}
    c, vetoes = {}, []
    for cat, v in p.items():
        f = E["contradict_factor"] if contra.get(cat) else E["corroborate_boost"] if cat in evidence["triggers"] else 1.0
        c[cat] = min(1.0, v * f)
        if f < 1:
            vetoes.append((cat, round(v, 3), round(c[cat], 3)))
    return c, vetoes


# ---- streaming client (§5a step 6) ----
def _field(text, name):
    m = re.search(rf'"{name}"\s*:\s*("(?:[^"\\]|\\.)*"?|null|-?\d+)', text)
    if not m:
        return None
    v = m.group(1)
    if v == "null":
        return None
    if v[0] == '"':
        return v[1:-1] if v.endswith('"') and len(v) > 1 else v[1:]
    return int(v)


def call(b64, hints, on_decide=None, stop_summary_at=None, cancel=None):
    """Stream one classification. on_decide(probs, category, subtype, t) is called as soon as the category is known
    (for suspicious_activity, once its subtype is, since severity depends on it); returning True stops the stream
    (confident-normal baseline). stop_summary_at() -> word limit or None, checked while the summary streams.
    cancel: threading.Event; set = close the stream (Ollama stops generating).
    Returns dict(category, subtype, people_count, summary, probs, timing, prompt_eval_count, ok, stopped) or raises on error/timeout."""
    body = {"model": V["model"], "stream": True, "think": V["think"], "keep_alive": V["keep_alive"], "format": SCHEMA,
            "logprobs": True, "top_logprobs": V["top_logprobs"],
            "options": {"temperature": V["temperature"], "num_predict": V["max_tokens"], "num_ctx": V["num_ctx"]},
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": hints, "images": b64 if isinstance(b64, list) else [b64]}]}
    t = {"t_vlm_start": time.time()}
    text, steps, probs, cat, decided, stopped, last = "", [], None, None, False, None, {}
    with httpx.stream("POST", V["base_url"] + V["endpoint"], json=body, timeout=V["timeout_s"]) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line:
                continue
            chunk = json.loads(line)
            if chunk.get("error"):
                raise RuntimeError(chunk["error"])
            t.setdefault("t_first_token", time.time())
            for tok in chunk.get("logprobs") or []:
                before = text
                text += tok["token"]
                if probs is None and _cats_for(text) is not None:  # inside the category value
                    steps.append((before, tok["token"], [(a["token"], a["logprob"]) for a in tok["top_logprobs"]]))
                    probs, cat = walk(steps)
                    if probs:
                        t["t_category"] = time.time()
            if chunk.get("done"):
                last = chunk
            if probs and not decided and (cat != "suspicious_activity" or re.search(r'"subtype"\s*:\s*("[^"]*"|null)', text)):
                decided = True
                if on_decide and on_decide(probs, cat, _field(text, "subtype"), t["t_category"]):
                    stopped = "category"
            summ = _field(text, "summary")
            lim = stop_summary_at() if stop_summary_at and summ else None
            if lim and len(summ.split()) > lim:
                stopped = "summary"
            if cancel is not None and cancel.is_set():
                stopped = stopped or "cancelled"
            if stopped or chunk.get("done"):
                break
            if time.time() - t["t_vlm_start"] > V["timeout_s"]:
                raise TimeoutError(f"VLM call > {V['timeout_s']} s")
    t["t_vlm_done"] = time.time()
    try:
        out = json.loads(text) if not stopped else {}
    except ValueError:
        out = None
    if out is None or (not stopped and out.get("category") not in CATS) or (stopped and not cat):  # §7.3: unparseable -> normal, 0
        return {"category": "normal", "subtype": None, "people_count": None, "summary": None, "probs": None,
                "timing": t, "prompt_eval_count": last.get("prompt_eval_count"), "ok": False, "stopped": stopped, "raw": text}
    sub = out.get("subtype", _field(text, "subtype"))
    cat = cat or out["category"]
    summary = out.get("summary") or (_field(text, "summary") if stopped == "summary" else None)
    if stopped == "summary" and summary:
        summary = " ".join(summary.split()[:lim]).rstrip(",;") + "…"
    return {"category": cat, "subtype": sub if sub in SUBTYPES[cat] else None,  # foreign subtype nulled (D49)
            "people_count": out.get("people_count", _field(text, "people_count")), "summary": summary,
            "probs": probs, "timing": t, "prompt_eval_count": last.get("prompt_eval_count"), "ok": True, "stopped": stopped, "raw": text}


if __name__ == "__main__":
    # 1. Prefix-tree walk: single-char "f" shared by fire_smoke/fighting, resolved by the next token.
    lp = math.log
    pre = '{\n  "category": "'
    steps = [(pre, "f", [("f", lp(0.6)), ("p", lp(0.3)), ("normal", lp(0.1)), ("!", -9999)]),
             (pre + "f", "ight", [("ight", lp(0.75)), ("ire", lp(0.25))])]
    p, c = walk(steps[:1])
    assert p is None, "f alone is ambiguous"
    p, c = walk(steps)
    assert c == "fighting" and abs(p["fighting"] - 0.45) < 1e-9 and abs(p["fire_smoke"] - 0.15) < 1e-9, p
    assert abs(p["person_down"] - 0.15) < 1e-9 and abs(p["property_damage"] - 0.15) < 1e-9 and abs(p["normal"] - 0.1) < 1e-9
    assert abs(sum(p.values()) - 1) < 1e-9
    p, c = walk([(pre, "crow", [("crow", lp(0.9)), ("c", lp(0.05)), ("n", lp(0.05))])])  # "c" -> crowd only
    assert c == "crowd_incident" and abs(p["crowd_incident"] - 0.95) < 1e-9, p
    # 2. Cross-check: nobody detected, model says fighting -> vetoed to half; person_down corroborated by a gate -> boosted.
    c, v = cross_check({"fighting": 0.8, "person_down": 0.2}, {"max_persons": 0, "door": False, "door_entries": 0,
                                                                  "triggers": {"person_down"}})
    assert c["fighting"] == 0.4 and c["person_down"] == 0.1 and v == [("fighting", 0.8, 0.4), ("person_down", 0.2, 0.1)], (c, v)
    c, v = cross_check({"fighting": 0.8}, {"max_persons": 1, "door": False, "door_entries": 0, "triggers": {"fighting"}})
    assert abs(c["fighting"] - 0.92) < 1e-9 and v == [], (c, v)   # one person seen (merged grapplers): no veto (D63)
    # 3. Letterbox: 4:3 and portrait frames keep their shape inside a 16:9 tile (D44).
    for shape in [(720, 960), (1280, 720), (360, 640)]:
        tile = letterbox(np.full((*shape, 3), 255, np.uint8), 288, 160)
        white = np.argwhere(tile[:, :, 0] == 255)
        hh, ww = white.max(0) - white.min(0) + 1
        assert tile.shape == (160, 288, 3) and abs(ww / hh - shape[1] / shape[0]) < 0.05, (shape, hh, ww)
    buf = [(i / 10, np.zeros((360, 640, 3), np.uint8), []) for i in range(40)]
    assert [round(f[0], 1) for f in pick_frames(buf)] == [1.9, 2.6, 3.2, 3.9], [f[0] for f in pick_frames(buf)]
    grid, b64 = mosaic(pick_frames(buf))
    assert grid.shape == (320, 576, 3)
    far = (0, np.zeros((360, 640, 3), np.uint8), [{"id": 7, "box": (300, 100, 330, 160)}])   # 60 px tall: crop
    ch, cw = track_crop(far, [7]).shape[:2]
    assert ch == 105 and abs(cw / ch - 16 / 9) < 0.02 and track_crop(far, [8]) is None, (ch, cw)   # 60 px x 1.75, 16:9
    assert track_crop((0, far[1], [{"id": 7, "box": (300, 100, 380, 300)}]), [7]) is None   # 200 px tall: no crop
    # 4. Live call on the sample clip's first frame: valid JSON, probabilities resolved, category known before done.
    cap = cv2.VideoCapture("data/demo/sample_bus.mp4"); frames = []
    for i in range(50):
        ok, f = cap.read()
        if i % 15 == 0:
            frames.append((i / 25, cv2.resize(f, (640, 480)), []))
    _, b64 = mosaic(frames[:4])
    call(b64, user_turn(4))  # warm-up
    seen = {}
    r = call(b64, user_turn(4),
             on_decide=lambda p, c, s, t: seen.update(p=p, c=c))
    t = r["timing"]
    print(json.dumps({k: r[k] for k in ("category", "subtype", "people_count", "summary", "prompt_eval_count")}),
          {k: round(v, 3) for k, v in sorted(r["probs"].items(), key=lambda kv: -kv[1])[:3]})
    print("ttft %.2f s, category %.2f s, done %.2f s" % (t["t_first_token"] - t["t_vlm_start"],
                                                         t["t_category"] - t["t_vlm_start"], t["t_vlm_done"] - t["t_vlm_start"]))
    assert r["ok"] and seen["c"] == r["category"] and abs(sum(r["probs"].values()) - 1) < 1e-6
    assert t["t_category"] < t["t_vlm_done"] and r["summary"]
    # 5. Stop at the category (confident-normal baseline path) is much shorter than the full call.
    r2 = call(b64, user_turn(4), on_decide=lambda *a: True)
    print("stopped at category: %.2f s" % (r2["timing"]["t_vlm_done"] - r2["timing"]["t_vlm_start"]))
    assert r2["stopped"] == "category" and r2["summary"] is None
    print("vlm self-check ok")
