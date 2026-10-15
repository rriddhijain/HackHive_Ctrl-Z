"""Gate rules: cheap detector heuristics that wake the VLM early (SPEC §5a step 3, §6.6).

Motion rules only so far (person_down, fighting); crowd, tailgating, loitering and scene_change join in P2.
A track history is a list of (t_capture, x1, y1, x2, y2), oldest first, in pixels of the 640 px frame
(the one coordinate system used everywhere, see app/detect.py). Only PERSON tracks are gated: the caller passes
Detector.person_hists(), never raw tracks that include bags.
All times come from t_capture differences, never frame counts, so a detector running below 10 FPS keeps
the same thresholds. Speeds are in box heights per second, so they don't depend on distance from the camera.
"""
import itertools
import math

SPEED_WINDOW_S = 0.3  # short enough that back-and-forth shoving doesn't cancel itself out

DEFAULTS = {"down_ratio": 1.2, "down_hold_s": 0.5, "drop_frac": 0.4, "drop_window_s": 0.5,
            "fight_speed": 1.0, "min_track_age_s": 0.5}


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
    """(score, hint) if the track just dropped fast or has stayed horizontal for down_hold_s, else None."""
    if not _old_enough(hist, cfg):
        return None
    now = hist[-1]
    # ponytail: fast drop also fires on sitting/bending; a false trigger only costs one VLM call, which decides
    a = _at(hist, now[0] - cfg["drop_window_s"])
    if a and now[2] - a[2] >= cfg["drop_frac"] * _h(a):
        frac = (now[2] - a[2]) / _h(a)
        return min(1.0, frac / (2 * cfg["drop_frac"])), f"top of box dropped {frac:.0%} of its height in {now[0] - a[0]:.1f} s"
    start = now[0] - cfg["down_hold_s"]
    if _at(hist, start) and all(_w(s) >= cfg["down_ratio"] * _h(s) for s in hist if s[0] >= start):
        return 1.0, f"has been horizontal for at least {cfg['down_hold_s']:.1f} s"
    return None


def fighting(tracks, cfg):
    """(track ids, speed) for the fastest pair of overlapping boxes moving at >= fight_speed, else None."""
    ok = {i: h for i, h in tracks.items() if _old_enough(h, cfg)}
    best = None
    for i, j in itertools.combinations(sorted(ok), 2):
        a, b = ok[i][-1], ok[j][-1]
        if min(a[3], b[3]) <= max(a[1], b[1]) or min(a[4], b[4]) <= max(a[2], b[2]):
            continue  # boxes don't overlap
        v = max(norm_speed(ok[i]), norm_speed(ok[j]))
        if v >= cfg["fight_speed"] and (best is None or v > best[1]):
            best = [i, j], v
    return best


def gate(camera_id, tracks, cfg):
    """Motion-rule Triggers (§7.4) for one camera on this frame. tracks: {track_id: history}."""
    out = []
    for tid, hist in tracks.items():
        if r := person_down(hist, cfg):
            out.append({"camera_id": camera_id, "rule": "person_down", "track_ids": [tid],
                        "score": round(r[0], 2), "hint": f"Track {tid} {r[1]}."})
    if f := fighting(tracks, cfg):
        (i, j), v = f
        out.append({"camera_id": camera_id, "rule": "fighting", "track_ids": [i, j],
                    "score": round(min(1.0, v / (2 * cfg["fight_speed"])), 2),
                    "hint": f"Tracks {i} and {j} overlap while moving at {v:.1f} body heights/s."})
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
    assert "horizontal" in person_down(lying, c)[1]

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
    print("gate self-check OK")
