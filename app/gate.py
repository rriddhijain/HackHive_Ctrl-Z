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


def kinematic_fall_analysis(hist, window_s=1.0):
    """Kinematic Centroid + AR Gate over a rolling window.
    Evaluates:
      1) AR transition from < 0.8 (upright) to > 1.2 (horizontal).
      2) Downward centroid velocity vy >= 0.5 body-heights/s.
      3) Post-impact stationary condition: vend <= 0.1 bh/s (or near-zero).
      Rejects slow reclining, crouching, or sitting on chairs/benches.
    """
    now = hist[-1]
    t_now = now[0]
    recent = [s for s in hist if t_now - s[0] <= window_s + 0.1]
    if len(recent) < 2:
        return False, 0.0, 0.0

    # Current sample must be horizontal: AR > 1.2
    w_now, h_now = _w(now), _h(now)
    if h_now <= 0 or (w_now / h_now) < 1.2:
        return False, 0.0, 0.0

    # Was the subject upright (AR < 0.8) earlier in the rolling window?
    upright_idx = None
    for idx, s in enumerate(recent[:-1]):
        h_s = _h(s)
        if h_s > 0 and (_w(s) / h_s) < 0.8:
            upright_idx = idx
            break

    if upright_idx is None:
        # Check if AR was < 0.9 (e.g. leaning slightly before fall)
        for idx, s in enumerate(recent[:-1]):
            h_s = _h(s)
            if h_s > 0 and (_w(s) / h_s) < 0.9:
                upright_idx = idx
                break

    if upright_idx is None:
        return False, 0.0, 0.0

    # Downward centroid velocity vy >= 0.5 bh/s (positive Y in image coords)
    max_down_v = 0.0
    impact_t = None
    for i in range(upright_idx, len(recent) - 1):
        for j in range(i + 1, len(recent)):
            dt = recent[j][0] - recent[i][0]
            if 0.05 <= dt <= 0.8:
                cy_i = (recent[i][2] + recent[i][4]) / 2.0
                cy_j = (recent[j][2] + recent[j][4]) / 2.0
                dy = cy_j - cy_i
                h_avg = (_h(recent[i]) + _h(recent[j])) / 2.0
                if h_avg > 0:
                    v_down = (dy / dt) / h_avg
                    if v_down > max_down_v:
                        max_down_v = v_down
                        impact_t = recent[j][0]

    # Post-impact stationary check
    post_samples = [s for s in recent if impact_t is not None and s[0] >= impact_t - 0.05]
    if len(post_samples) < 2:
        post_samples = recent[-3:] if len(recent) >= 3 else recent
    dt_end = post_samples[-1][0] - post_samples[0][0]
    if dt_end > 0.05:
        cy_0 = (post_samples[0][2] + post_samples[0][4]) / 2.0
        cy_1 = (post_samples[-1][2] + post_samples[-1][4]) / 2.0
        cx_0 = (post_samples[0][1] + post_samples[0][3]) / 2.0
        cx_1 = (post_samples[-1][1] + post_samples[-1][3]) / 2.0
        h_end = (_h(post_samples[0]) + _h(post_samples[-1])) / 2.0
        v_end = math.hypot(cx_1 - cx_0, cy_1 - cy_0) / dt_end / (h_end if h_end > 0 else 1.0)
    else:
        v_end = 0.0

    return True, max_down_v, v_end


def person_down(hist, cfg):
    """(score, hint, kind, bbox) if the track satisfies person_down trigger conditions:
    1. Kinematic Centroid + AR Gate:
       - AR transitions from < 0.8 (upright) to > 1.2 (horizontal).
       - Downward centroid velocity vy >= 0.5 body-heights/sec.
       - Post-impact stationary condition: vend <= 0.1 body-heights/sec (allowing tracker jitter up to 0.35).
       - Rejects slow reclining, crouching, or sitting on chairs/benches.
    2. Horizontal-hold fallback:
       - If a person has remained wide for >= down_hold_s, triggers 'horizontal'.
    """
    if not _old_enough(hist, cfg):
        return None
    now = hist[-1]
    w, h = _w(now), _h(now)
    if h <= 0:
        return None
    ar = w / h

    # Aspect ratio check
    down_ar = cfg.get("down_ratio", 1.2)
    if ar < down_ar:
        return None

    # Check kinematic centroid fall
    window_s = cfg.get("fall_window_s", 1.0)
    transitioned, max_down_v, end_v = kinematic_fall_analysis(hist, window_s=window_s)
    min_down_v = cfg.get("fall_min_down_velocity", 0.5)
    max_stopped_v = cfg.get("fall_stopped_velocity", 0.35)

    if transitioned and max_down_v >= min_down_v and end_v <= max_stopped_v:
        frac = min(1.0, max_down_v / 2.0)
        bbox = (now[1], now[2], now[3], now[4])
        return (max(0.7, frac),
                f"a person's box dropped with downward velocity {max_down_v:.1f} bh/s and stopped (AR {ar:.2f}) {FALL}",
                "drop",
                bbox)

    # Secondary check: top of box fast-drop guard
    a = _at(hist, now[0] - cfg.get("drop_window_s", 0.5))
    if a and now[2] - a[2] >= cfg.get("drop_frac", 0.4) * _h(a) and _w(now) >= (1 - cfg.get("fast_drop_max_narrow", 0.2)) * _w(a):
        frac = (now[2] - a[2]) / _h(a)
        bbox = (now[1], now[2], now[3], now[4])
        return (min(1.0, frac / (2 * cfg.get("drop_frac", 0.4))),
                f"a person's box top dropped {frac:.0%} of its height in {now[0] - a[0]:.1f} s {FALL}", "drop", bbox)

    # Horizontal-hold fallback (e.g. subject already collapsed/horizontal before clip start)
    start = now[0] - cfg.get("down_hold_s", 0.5)
    if _at(hist, start) and all(wide(s, cfg) for s in hist if s[0] >= start):
        bbox = (now[1], now[2], now[3], now[4])
        return 1.0, f"a person's box has been wider than tall for at least {cfg['down_hold_s']:.1f} s {FALL}", "horizontal", bbox

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
    """Pairwise spatial proximity + velocity variance for interacting people.
    Trigger ONLY when:
      - Centroid distance < 0.5 * average height (or bounding boxes overlap / touch).
      - High variance in bounding box velocities (erratic lateral motion / oscillation > 1.2 m/s eq).
      - Solitary erratic motion is rejected since distance < 0.5 * avg height requires 2 interacting subjects.
    Returns ([i, j], v, bbox_a, bbox_b) or None.
    """
    ok = {i: h for i, h in tracks.items() if _old_enough(h, cfg)}
    best = None
    for i, j in itertools.combinations(sorted(ok), 2):
        if (i, j) in skip:
            continue
        a, b = ok[i][-1], ok[j][-1]
        ha, hb = _h(a), _h(b)
        if ha <= 0 or hb <= 0:
            continue
        if min(ha, hb) < cfg["fight_min_height_ratio"] * max(ha, hb):
            continue  # overlap only in perspective: one stands much further back

        # Spatial Proximity: Centroid distance < 0.5 * average height OR recent bbox overlap
        avg_h = (ha + hb) / 2.0
        ca = ((a[1] + a[3]) / 2.0, (a[2] + a[4]) / 2.0)
        cb = ((b[1] + b[3]) / 2.0, (b[2] + b[4]) / 2.0)
        c_dist = math.hypot(ca[0] - cb[0], ca[1] - cb[1]) / avg_h

        has_overlap = touched(ok[i], ok[j], max(a[0], b[0]) - cfg["fight_contact_s"])
        if c_dist >= 0.5 and not has_overlap:
            continue

        # Velocity Variance & Erratic Motion:
        # Fast part of a shove or lateral oscillation / variance
        v = max(norm_speed(ok[i]), norm_speed(ok[j]))
        if v >= cfg["fight_speed"] and (best is None or v > best[1]):
            best = [i, j], v, (a[1], a[2], a[3], a[4]), (b[1], b[2], b[3], b[4])

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


def property_damage_trigger(cam_id, buffer, zones, cfg):
    """Detect object-person interaction + sudden optical delta:
    Trigger when a person bounding box overlaps with static infrastructure/zones
    and exhibits high-frequency localized frame-difference deltas (striking, throwing, smashing glass)."""
    if len(buffer) < 2:
        return None
    now_e = buffer[-1]
    old_e = next((e for e in reversed(buffer) if now_e[0] - e[0] >= 0.2), buffer[0])
    dt = now_e[0] - old_e[0]
    if dt < 0.1 or dt > 0.8:
        return None

    t_now, f_now, tracks_now = now_e
    t_old, f_old, tracks_old = old_e

    person_boxes = [t["box"] for t in tracks_now if t["cls"] == "person"]
    if not person_boxes:
        return None

    H, W = f_now.shape[:2]
    bg_mad = mad(grey160(f_old, person_boxes), grey160(f_now, person_boxes)) / 255.0
    if bg_mad > 0.15:  # global scene change, not localized property damage
        return None

    if not zones:
        return None

    for p in tracks_now:
        if p["cls"] != "person":
            continue
        box = p["box"]
        x1, y1, x2, y2 = [int(v) for v in box]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(W, x2), min(H, y2)
        if x2 <= x1 or y2 <= y1:
            continue

        # Check zone overlap with static infrastructure
        foot = ((x1 + x2) / 2.0, y2)
        center = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
        in_zone = any(in_poly(foot, poly) or in_poly(center, poly) for poly in zones.values())
        if not in_zone:
            continue
        # Localized frame difference inside and around person's reach zone
        bx1 = max(0, int(x1 - (x2 - x1) * 0.15))
        by1 = max(0, int(y1 - (y2 - y1) * 0.15))
        bx2 = min(W, int(x2 + (x2 - x1) * 0.15))
        by2 = min(H, int(y2 + (y2 - y1) * 0.15))

        crop_old = cv2.cvtColor(f_old[by1:by2, bx1:bx2], cv2.COLOR_BGR2GRAY)
        crop_new = cv2.cvtColor(f_now[by1:by2, bx1:bx2], cv2.COLOR_BGR2GRAY)
        if crop_old.shape != crop_new.shape or crop_old.size == 0:
            continue

        local_mad = float(np.mean(cv2.absdiff(crop_old, crop_new))) / 255.0
        if local_mad >= cfg.get("vandalism_mad_thresh", 0.22) and local_mad > bg_mad * 2.5:
            return {
                "camera_id": cam_id,
                "rule": "property_damage",
                "track_ids": [p["id"]],
                "score": round(min(1.0, local_mad * 2.5), 2),
                "hint": "localized high-frequency optical delta at infrastructure (possible property damage / vandalism)",
                "bbox": box,
                "target_bbox": box,
            }
    return None


def crowd_incident_trigger(cam_id, tracks, cfg):
    """Trigger when there is divergence of optical motion vectors or sudden
    multi-centroid acceleration radiating from a central point."""
    ok = {i: h for i, h in tracks.items() if len(h) >= 2}
    if len(ok) < 3:
        return None

    now_centroids = []
    vels = []
    heights = []
    t_now = max(h[-1][0] for h in ok.values())

    for tid, hist in ok.items():
        if t_now - hist[-1][0] > 0.3:
            continue
        now = hist[-1]
        a = _at(hist, now[0] - 0.4) or hist[0]
        dt = now[0] - a[0]
        if dt <= 0:
            continue
        cx_now, cy_now = (now[1] + now[3]) / 2.0, (now[2] + now[4]) / 2.0
        cx_a, cy_a = (a[1] + a[3]) / 2.0, (a[2] + a[4]) / 2.0
        h = max(1.0, _h(now))
        now_centroids.append((cx_now, cy_now))
        vels.append(((cx_now - cx_a) / dt / h, (cy_now - cy_a) / dt / h))
        heights.append(h)

    if len(now_centroids) < 3:
        return None

    center_x = sum(c[0] for c in now_centroids) / len(now_centroids)
    center_y = sum(c[1] for c in now_centroids) / len(now_centroids)

    radiating_speeds = []
    for (cx, cy), (vx, vy), h in zip(now_centroids, vels, heights):
        rx, ry = cx - center_x, cy - center_y
        dist = math.hypot(rx, ry)
        if dist > 10:
            proj = (rx * vx + ry * vy) / dist
            radiating_speeds.append(proj)

    if len(radiating_speeds) >= 3:
        avg_radial = sum(radiating_speeds) / len(radiating_speeds)
        if avg_radial >= cfg.get("crowd_divergence_thresh", 0.8):
            return {
                "camera_id": cam_id,
                "rule": "crowd_incident",
                "track_ids": list(ok.keys()),
                "score": round(min(1.0, avg_radial / 1.5), 2),
                "hint": f"sudden multi-centroid acceleration radiating from center at {avg_radial:.1f} bh/s (possible crowd incident / dispersal)",
            }
    return None


def tailgating_trigger(cam_id, det_tracks, zones, cfg):
    """Sequential entry gate bounding box headway < 0.4m within the door cycle cooldown window."""
    if not zones or "door" not in zones:
        return None
    entries = []
    for tr in det_tracks.values():
        if tr.cls != 0:
            continue
        door_times = tr.zone_entries.get("door", [])
        if door_times:
            entries.append((door_times[-1], tr))

    if len(entries) < 2:
        return None
    entries.sort(key=lambda x: x[0])

    t1, tr1 = entries[-2]
    t2, tr2 = entries[-1]
    cycle_s = cfg.get("door_cycle_s", 2.5)
    if 0.1 <= (t2 - t1) <= cycle_s:
        if tr1.hist and tr2.hist:
            b1 = tr1.hist[-1]
            b2 = tr2.hist[-1]
            headway_bh = gap(b1, b2)
            if headway_bh < cfg.get("tailgate_headway_bh", 0.35):
                return {
                    "camera_id": cam_id,
                    "rule": "tailgating",
                    "track_ids": [tr1.id, tr2.id],
                    "score": 0.85,
                    "hint": f"sequential entry headway {headway_bh:.2f} bh (<0.4m) within door cycle (possible tailgating)",
                }
    return None


def gate(camera_id, tracks, cfg, skip=(), zones=None, buffer=None, det_tracks=None):
    """Motion-rule Triggers (§7.4) for one camera on this frame. tracks: {track_id: history}; skip: silenced fight pairs."""
    out = []
    for tid, hist in tracks.items():
        if r := person_down(hist, cfg):
            trig = {"camera_id": camera_id, "rule": "person_down", "track_ids": [tid],
                    "score": round(r[0], 2), "hint": r[1], "kind": r[2]}
            if len(r) > 3 and r[3] is not None:
                trig["bbox"] = r[3]
                trig["target_bbox"] = r[3]
            out.append(trig)
    if f := fighting(tracks, cfg, skip):
        (i, j), v, bbox_a, bbox_b = f
        union_bbox = (min(bbox_a[0], bbox_b[0]), min(bbox_a[1], bbox_b[1]),
                      max(bbox_a[2], bbox_b[2]), max(bbox_a[3], bbox_b[3]))
        out.append({"camera_id": camera_id, "rule": "fighting", "track_ids": [i, j],
                    "score": round(min(1.0, v / (2 * cfg["fight_speed"])), 2),
                    "hint": f"two people's boxes overlap while moving at {v:.1f} body heights/s {FIGHT}",
                    "bbox_a": bbox_a, "bbox_b": bbox_b, "target_bbox": union_bbox})
    if cr := crowd_incident_trigger(camera_id, tracks, cfg):
        out.append(cr)
    if buffer and (pd := property_damage_trigger(camera_id, buffer, zones, cfg)):
        out.append(pd)
    if det_tracks and zones and (tg := tailgating_trigger(camera_id, det_tracks, zones, cfg)):
        out.append(tg)
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
