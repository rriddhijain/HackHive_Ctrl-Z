"""Gate rules: cheap detector heuristics that wake the VLM early (SPEC §5a step 3, §6.6).

Rules: person_down, fighting (person tracks) and scene_change (pixels, person boxes masked out).
Crowd, loitering and tailgating are not wired yet (crowd/loitering have no §6.6 rule; tailgating is F, D55).
A track history is a list of (t_capture, x1, y1, x2, y2), oldest first, in pixels of the 640 px frame
(the one coordinate system used everywhere, see app/detect.py). Only PERSON tracks are gated: the caller passes
Detector.person_hists(), never raw tracks that include bags.
All times come from t_capture differences, never frame counts, so a detector running below 10 FPS keeps
the same thresholds. Speeds are in box heights per second, so they don't depend on distance from the camera.
"""
import itertools
import math

import cv2
import numpy as np

SPEED_WINDOW_S = 0.3  # short enough that back-and-forth shoving doesn't cancel itself out
# Hint hypotheses name the look-alikes too (D86): "(possible fight)" alone made the model call a crowd running, a helper
# next to a fallen person and people talking a fight (base pass: 5/29 gate calls right; this wording 14/29, same fights).
FALL = "(a fall, or someone kneeling, bending, crouching or sitting: judge from the frames)"
FIGHT = "(a fight, or people hugging, helping someone up, working side by side, or a crowd moving: judge from the frames)"

def wide(s, cfg):
    """Box (t, x1, y1, x2, y2) at least down_ratio times wider than tall."""
    return _w(s) >= cfg["down_ratio"] * _h(s)


DEFAULTS = {"down_ratio": 1.2, "down_hold_s": 0.5, "drop_frac": 0.4, "drop_window_s": 0.5, "fast_drop_max_narrow": 0.2,
            "fight_speed": 0.6, "fight_min_height_ratio": 0.5, "fight_contact_s": 0.5, "min_track_age_s": 0.5}


def _h(s):
    return s[4] - s[2]


def _w(s):
    return s[3] - s[1]


def _at(hist, t):
    """Latest sample at or before t, or None if the history doesn't reach back that far."""
    for s in reversed(hist):
        if s[0] <= t:
            return s
    return None


def _old_enough(hist, cfg):
    # A fresh ID is often a ByteTrack ID switch, whose first jump looks like a speed spike.
    return hist[-1][0] - hist[0][0] >= cfg["min_track_age_s"]


def norm_speed(hist, window_s=SPEED_WINDOW_S):
    """Centroid speed over the last window_s, in box heights per second."""
    a, b = _at(hist, hist[-1][0] - window_s) or hist[0], hist[-1]
    dt = b[0] - a[0]
    if dt <= 0:
        return 0.0
    dx = (b[1] + b[3] - a[1] - a[3]) / 2
    dy = (b[2] + b[4] - a[2] - a[4]) / 2
    return math.hypot(dx, dy) / dt / ((_h(a) + _h(b)) / 2)


def person_down(hist, cfg):
    """(score, hint, kind) if the track just dropped fast ("drop") or has stayed horizontal for down_hold_s ("horizontal")."""
    if not _old_enough(hist, cfg):
        return None
    now = hist[-1]
    # ponytail: fast drop also fires on sitting/bending; a false trigger only costs one VLM call, which decides
    a = _at(hist, now[0] - cfg["drop_window_s"])
    # A box that got narrower while its top dropped is occlusion or someone walking away, not a fall (D61);
    # fast_drop_max_narrow: 1.0 turns this guard off.
    if a and now[2] - a[2] >= cfg["drop_frac"] * _h(a) and _w(now) >= (1 - cfg["fast_drop_max_narrow"]) * _w(a):
        frac = (now[2] - a[2]) / _h(a)
        return (min(1.0, frac / (2 * cfg["drop_frac"])),
                f"a person's box top dropped {frac:.0%} of its height in {now[0] - a[0]:.1f} s {FALL}", "drop")
    start = now[0] - cfg["down_hold_s"]
    if _at(hist, start) and all(wide(s, cfg) for s in hist if s[0] >= start):
        return 1.0, f"a person's box has been wider than tall for at least {cfg['down_hold_s']:.1f} s {FALL}", "horizontal"
    return None


def gap(a, b):
    """Centroid distance of two boxes (t, x1, y1, x2, y2) in body heights."""
    return math.hypot(a[1] + a[3] - b[1] - b[3], a[2] + a[4] - b[2] - b[4]) / (_h(a) + _h(b))


def overlap(a, b):
    return min(a[3], b[3]) > max(a[1], b[1]) and min(a[4], b[4]) > max(a[2], b[2])


def touched(hi, hj, since):
    """The two tracks' boxes overlapped on some frame at or after `since` (both boxes from that same frame)."""
    at_j = {s[0]: s for s in hj}
    return any(s[0] in at_j and overlap(s, at_j[s[0]]) for s in hi if s[0] >= since)


def fighting(tracks, cfg, skip=()):
    """(track ids, speed) for the fastest pair of similar-height boxes (same depth) that overlapped within the last
    fight_contact_s, with either moving at >= fight_speed: a shove's fast part comes just after the boxes part (D72).
    skip: pairs (i, j), i < j, silenced after a confident-normal verdict (D64)."""
    ok = {i: h for i, h in tracks.items() if _old_enough(h, cfg)}
    best = None
    for i, j in itertools.combinations(sorted(ok), 2):
        if (i, j) in skip:
            continue
        a, b = ok[i][-1], ok[j][-1]
        if min(_h(a), _h(b)) < cfg["fight_min_height_ratio"] * max(_h(a), _h(b)):
            continue  # overlap only in the picture: one stands much further back (D72)
        if not touched(ok[i], ok[j], max(a[0], b[0]) - cfg["fight_contact_s"]):
            continue
        v = max(norm_speed(ok[i]), norm_speed(ok[j]))
        if v >= cfg["fight_speed"] and (best is None or v > best[1]):
            best = [i, j], v
    return best


def grey160(frame, boxes=()):
    """160 px wide grey copy (scene_change and change-gated baselines compare these); boxes (frame pixels) blanked."""
    g = cv2.cvtColor(cv2.resize(frame, (160, round(frame.shape[0] * 160 / frame.shape[1]))), cv2.COLOR_BGR2GRAY)
    k = 160 / frame.shape[1]
    for x1, y1, x2, y2 in boxes:
        g[int(y1 * k):int(y2 * k) + 1, int(x1 * k):int(x2 * k) + 1] = 0
    return g


def mad(a, b):
    """Mean absolute difference of two grey images, 0-255."""
    return float(np.mean(cv2.absdiff(a, b))) if a.shape == b.shape else 255.0


def scene_change(old, new, cfg):
    """old/new: buffer entries (t, frame, tracks) ~0.5 s apart. MAD of the non-person pixels, as a fraction of 255."""
    boxes = [t["box"] for e in (old, new) for t in e[2] if t["cls"] == "person"]
    d = mad(grey160(old[1], boxes), grey160(new[1], boxes)) / 255
    return d if d > cfg["scene_change_frac"] else None


def gate(camera_id, tracks, cfg, skip=()):
    """Motion-rule Triggers (§7.4) for one camera on this frame. tracks: {track_id: history}; skip: silenced fight pairs.
    Hint text (D77, D86): the numbers and the hypothesis with its look-alikes; no track ids, never the word gate."""
    out = []
    for tid, hist in tracks.items():
        if r := person_down(hist, cfg):
            out.append({"camera_id": camera_id, "rule": "person_down", "track_ids": [tid],
                        "score": round(r[0], 2), "hint": r[1], "kind": r[2]})
    if f := fighting(tracks, cfg, skip):
        (i, j), v = f
        out.append({"camera_id": camera_id, "rule": "fighting", "track_ids": [i, j],
                    "score": round(min(1.0, v / (2 * cfg["fight_speed"])), 2),
                    "hint": f"two people's boxes overlap while moving at {v:.1f} body heights/s {FIGHT}"})
    return out


if __name__ == "__main__":
    c = DEFAULTS
    t = [i / 10 for i in range(11)]  # 1 s at 10 FPS

    standing = [(ti, 100, 100, 150, 300) for ti in t]  # 200 px tall, still
    assert gate("cam1", {1: standing}, c) == []

    # Fall: top drops 120 px (0.6 h) in 0.3 s at the end, bottom stays put.
    fall = standing[:8] + [(t[8], 100, 160, 170, 300), (t[9], 90, 200, 190, 300), (t[10], 60, 220, 220, 300)]
    tr = gate("cam1", {1: fall}, c)
    assert [x["rule"] for x in tr] == ["person_down"] and "dropped" in tr[0]["hint"], tr

    # Lying still for 0.6 s (no drop inside the window) → horizontal-hold path.
    lying = [(ti, 60, 240, 220, 300) for ti in t]
    assert person_down(lying, c)[2] == "horizontal" and "wider than tall" in person_down(lying, c)[1]
    # D77/D86 hint contract: no track ids, never the word gate/track (the model narrated "a track gate drops"); the
    # hypothesis names its look-alikes and leaves the call to the frames.
    for h in (tr[0]["hint"], person_down(lying, c)[1]):
        assert not any(w in h.lower() for w in ("track", "gate")) and h.endswith("judge from the frames)"), h

    # Occlusion: top drops 45 % but the box narrows 94 -> 60 px (sample_bus.mp4 track 3) -> no trigger; guard off -> fires.
    occl = standing[:8] + [(t[8], 100, 200, 180, 300), (t[9], 105, 230, 170, 300), (t[10], 110, 290, 170, 300)]
    occl = [(s[0], 100, 100, 194, 300) if i < 8 else s for i, s in enumerate(occl)]
    assert person_down(occl, c) is None and person_down(occl, c | {"fast_drop_max_narrow": 1.0})

    # Same fall on a brand-new track (ID switch) → ignored.
    assert person_down(fall[-3:], c) is None

    # Distance independence: the same motion at half scale gives the same speed.
    far = [(s[0], s[1] / 2, s[2] / 2, s[3] / 2, s[4] / 2) for s in fall]
    assert abs(norm_speed(fall) - norm_speed(far)) < 1e-9

    # Two overlapping people, one shoving at 1.5 heights/s → fighting; the same pair standing still → nothing.
    a = [(ti, 100, 100, 150, 300) for ti in t]
    x = [200 - 300 * max(0.0, ti - 0.7) for ti in t]  # still, then lunges at 300 px/s into track 1
    b = [(ti, xi, 100, xi + 50, 300) for ti, xi in zip(t, x)]
    tr = gate("cam1", {1: a, 2: b}, c)
    assert [x["rule"] for x in tr] == ["fighting"] and tr[0]["track_ids"] == [1, 2], tr
    assert gate("cam1", {1: a, 2: [(ti, 130, 100, 180, 300) for ti in t]}, c) == []
    assert gate("cam1", {1: a, 2: b}, c, skip={(1, 2)}) == []          # silenced pair (D64)
    far_b = [(s[0], s[1], 100, s[3], 180) for s in b]                    # same lunge, box 0.4 as tall: further back (D72)
    assert gate("cam1", {1: a, 2: far_b}, c) == []
    # Shove (D72): boxes touch until 0.7 s, then track 2 is pushed away at 3 body heights/s and they no longer overlap.
    shove = [(ti, x, 100, x + 50, 300) for ti, x in ((ti, 140 + 600 * max(0.0, ti - 0.7)) for ti in t)]
    assert [x["rule"] for x in gate("cam1", {1: a, 2: shove}, c)] == ["fighting"]
    early = [(ti, x, 100, x + 50, 300) for ti, x in ((ti, 140 + 300 * max(0.0, ti - 0.4)) for ti in t)]
    assert gate("cam1", {1: a, 2: early}, c) == []                      # last contact 0.6 s ago: outside fight_contact_s
    runner = [(ti, 400 + 300 * ti, 100, 450 + 300 * ti, 300) for ti in t]
    assert gate("cam1", {1: a, 2: runner}, c) == []                     # fast, but never touched
    assert abs(gap(a[-1], b[-1]) - 0.05) < 1e-9   # centroids 10 px apart, 200 px tall
    # Scene change: lights off (whole frame darkens) fires; a person moving (masked out) doesn't.
    lit, dark = np.full((360, 640, 3), 180, np.uint8), np.full((360, 640, 3), 20, np.uint8)
    walker = lit.copy(); walker[100:300, 300:360] = 0
    p = [{"cls": "person", "box": (300, 100, 360, 300)}]
    assert scene_change((0, lit, p), (0.5, dark, p), {"scene_change_frac": 0.25})
    assert scene_change((0, lit, p), (0.5, walker, p), {"scene_change_frac": 0.25}) is None
    print("gate self-check OK")
