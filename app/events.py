"""Event manager: opens, updates and closes incidents from per-observation probabilities (SPEC §6.4, §6.5, §5a steps 7, 9, 10).

decide() runs at t_category (early decision): it updates the camera's 3-observation window and opens events, so the
alert fires before the summary exists. finish() runs at t_vlm_done: summary, subtype, track ids, key frames.
tick() runs every second: an event closes only after 2 non-supporting observations AND 8 s since its last support,
or after its camera has been down for 8 s; a camera starved of model time keeps its events open (D43).

person_down second look (events.down_guard, proposed D83): when a person_down observation opens an event but the
detector evidence says it cannot vouch for the scene (detector_blind: people seen in < blind_frac of the 4 s buffer)
or that people were interacting (a fighting gate fired in the 4 s buffer), the alert still fires AT ONCE (no added
latency) but the event is marked unverified and the caller asks for a re-look (P4, the whole 4 s buffer, question:
fight vs fall vs lying normally). The re-look is a second model vote: fighting -> a fighting event opens (or the open
one is used) and the person_down event is marked dismissed, reason "relook" (SPEC E-9), never rewritten or deleted;
the two rows point at each other through related_event_id, so the history shows "alerted as person down, re-checked,
reclassified as fighting". A CONFIDENT normal (c >= 0.80) -> the person_down event is marked dismissed the same way;
anything else confirms it. A re-look that arrives after the original closed leaves it as it was. A re-look that never runs (stale, busy GPU) changes
nothing: the alert stands. person_down is never relabelled fighting without a model vote for fighting.
"""
import threading
import time
from collections import defaultdict, deque

from app.config import CFG
from app.vlm import CATS, GATE_CAT, severity

# Categories no gate can corroborate open only through the window, so they get a lower window threshold (D77).
UNGATED = set(CATS[:-1]) - set(GATE_CAT.values()) - {"fire_smoke"}

E = CFG["events"]


class EventManager:
    def __init__(self, db, emit=lambda kind, data: None, cam_names=None):
        self.db, self.emit, self.cam_names = db, emit, cam_names or {}
        self.win = defaultdict(lambda: deque(maxlen=E["window_n"]))   # camera -> last 3 observations' c maps
        self.open = {}                                                 # (camera, category) -> event dict
        self.hold = {}                                                 # (camera, category) -> no new event until (FR-25)
        self.pending = {}                                              # camera -> unverified person_down (down_guard)
        self.new_holds = set()                                         # cameras whose unverified event needs a re-look
        self.held_log = deque(maxlen=500)                              # (camera, outcome, ts) for reports
        self.lock = threading.Lock()

    def is_open(self, cam, cat):
        return (cam, cat) in self.open

    def has_open(self, cam):
        return any(k[0] == cam for k in self.open)

    def guarded(self, evidence):
        """Why a person_down from this evidence needs a second look, or None (down_guard)."""
        g = E.get("down_guard") or {}
        if not g.get("enabled") or not evidence:
            return None
        if evidence.get("detector_blind"):
            return "detector_blind"
        # Interaction = a fighting gate fired in the last 4 s (similar-height boxes in contact, moving fast). Plain box
        # overlap is NOT enough: people at different depths overlap on screen in almost every call (idle_60s 19/19,
        # sample_bus 4/4 in bench.diagnose), which would hold every real fall in a busy scene.
        if "fighting" in (evidence.get("triggers") or ()):
            return "interaction"
        return None

    def take_new_hold(self, cam):
        with self.lock:
            if cam in self.new_holds:
                self.new_holds.discard(cam)
                return dict(self.pending[cam]) if cam in self.pending else None
        return None

    def _new_event(self, cam, cat, subtype, sev, c_cat, c, ts, t_ref, t_alert, opened_by=None):
        ev = {"camera_id": cam, "camera_name": self.cam_names.get(cam, cam), "category": cat,
              "subtype": subtype, "severity": sev, "start_ts": ts, "end_ts": ts,
              "peak_confidence": c_cat, "summary": None, "keyframe_paths": [], "track_ids": [],
              "status": "open", "n_obs": 1, "time_to_alert_ms": round((t_alert - t_ref) * 1000),
              "_last_support": ts, "_nonsupport": 0, "_peak_now": True, "_t_alert": t_alert,
              "_probs": sorted(c.items(), key=lambda kv: -kv[1])[:3], "opened_by": opened_by}
        ev["id"] = self.db.insert("events", ev)
        self.open[(cam, cat)] = ev
        return ev

    def decide(self, cam, c, subtype, triggers, ts, t_ref, t_alert=None, evidence=None, relook=False):
        """c: evidence-adjusted probabilities of this observation; triggers: categories a gate trigger supports;
        ts: observation time (newest frame's t_capture); t_ref: gate trigger time or baseline request time.
        evidence: scheduler.evidence() (down_guard); relook: this observation is a P4 second look.
        Returns (opened events, supported events)."""
        t_alert = t_alert or time.time()
        top = max(c, key=c.get)
        opened, supported = [], []
        why = self.guarded(evidence) if not relook else None
        retracted = []
        with self.lock:
            held = self.pending.pop(cam, None) if relook else None
            if relook:
                self.new_holds.discard(cam)
                pd = self.open.get((cam, "person_down"))
                if not held or pd is None or pd["id"] != held["eid"]:
                    # Nothing left to judge (expired, closed, dismissed by the operator, camera removed): the
                    # history stays exactly as it was and this vote changes nothing, not even the window.
                    self.held_log.append((cam, "relook_after_close" if held else "relook_stale", ts))
                    return [], []
                self.held_log.append((cam, f"relook:{top}", ts))
            win = self.win[cam]
            win.append(c)
            for (cm, cat), ev in self.open.items():
                if cm != cam:
                    continue
                if c[cat] >= E["close_c"]:      # supports the event: extend it (§6.4)
                    ev.update(end_ts=ts, _last_support=ts, _nonsupport=0, n_obs=ev["n_obs"] + 1)
                    ev["_peak_now"] = c[cat] > ev["peak_confidence"]
                    ev["peak_confidence"] = max(ev["peak_confidence"], c[cat])
                    supported.append(ev)
                else:
                    ev["_nonsupport"] += 1
            for cat in CATS[:-1]:
                if (cam, cat) in self.open or self.hold.get((cam, cat), 0) > ts:
                    continue
                sev = severity(cat, subtype if cat == top else None)
                single = E["open_single_critical"] if sev == "critical" else E["open_single_other"]
                corroborated = cat in triggers or cat == "fire_smoke" or (relook and cat in ("person_down", "fighting"))
                S = sum(w[cat] for w in win) / len(win)
                thr = E["open_window_ungated"] if cat in UNGATED else E["open_window"]
                if held and cat == "person_down":
                    continue                                # the second look never re-opens what it is judging
                if (c[cat] >= single and corroborated) or (len(win) >= 2 and S >= thr):
                    fight = self.open.get((cam, "fighting"))
                    if cat == "person_down" and why and fight and fight.get("related_event_id"):
                        # A second look already re-labelled this scene's person_down as this fight: another
                        # unverified person_down while it is open is the same incident, not a new alert.
                        self.held_log.append((cam, f"covered_by:{fight['id']}", ts))
                        continue
                    ev = self._new_event(cam, cat, subtype if cat == top else None, sev, c[cat], c, ts,
                                         held["t_ref"] if held else t_ref, t_alert, "relook" if relook else None)
                    opened.append(ev)
                    if cat == "person_down" and why:        # alert now, verify in the background (no added latency)
                        ev["opened_by"] = "unverified:" + why
                        self.pending[cam] = {"eid": ev["id"], "why": why, "t_ref": t_ref,
                                             "deadline": t_alert + (E.get("down_guard") or {}).get("verify_s", 10.0)}
                        self.new_holds.add(cam)
                        self.held_log.append((cam, "unverified:" + why, ts))
            linked = None
            if held:                                        # pd is the open event this re-look judges
                fight = next((e for e in opened if e["category"] == "fighting"), None) if top == "fighting" else None
                if top == "fighting" and fight is None:
                    fight = self.open.get((cam, "fighting"))
                    if fight is None and self.hold.get((cam, "fighting"), 0) <= ts:   # never over an operator dismissal
                        # A second vote for fighting below the single-observation bar still opens it: two votes, one incident.
                        fight = self._new_event(cam, "fighting", None, severity("fighting", None), c["fighting"], c,
                                                ts, held["t_ref"], t_alert, "relook")
                        opened.append(fight)
                if fight is not None or (top == "normal" and c["normal"] >= 0.80):
                    # Re-labelled or retracted, never rewritten: the original row stays, marked and linked (E-9).
                    self.open.pop((cam, "person_down"))
                    pd.update(status="dismissed", dismiss_reason="relook")
                    if fight is not None:
                        pd["related_event_id"], fight["related_event_id"] = fight["id"], pd["id"]
                        linked = fight
                    retracted.append(pd)
                    self.held_log.append((cam, f"reclassified:{held['eid']}->{fight['id']}" if fight else "retracted:normal", ts))
                elif top != "fighting":
                    pd["opened_by"] = "verified"
                    self.held_log.append((cam, "verified", ts))
                else:
                    self.held_log.append((cam, "relook_fighting_on_hold", ts))   # left unverified, unchanged
        for ev in opened:
            self.emit("alert", ev)
        for ev in retracted:                                # E-9: dismissed after re-check, linked to its replacement
            self.db.update("events", ev["id"], {"status": "dismissed", "dismiss_reason": "relook",
                                                "related_event_id": ev.get("related_event_id")})
            self.emit("event_close", ev)
        if linked is not None:
            self.db.update("events", linked["id"], {"related_event_id": linked["related_event_id"]})
            if linked not in opened:
                self.emit("event_update", linked)
        return opened, supported

    def finish(self, cam, obs, events, keyframes):
        """At t_vlm_done: obs = the stored observation fields; events = (opened + supported) from decide().
        keyframes(event_id) -> paths, called when this observation is the event's new peak. Returns the event_id to attach."""
        best = None
        for ev in sorted(events, key=lambda e: -e["peak_confidence"]):
            ev["track_ids"] = sorted(set(ev["track_ids"]) | set(obs.get("track_ids") or []))
            row = {"end_ts": ev["end_ts"], "n_obs": ev["n_obs"], "peak_confidence": ev["peak_confidence"],
                   "track_ids": ev["track_ids"]}
            if ev.pop("_peak_now", False):  # a new peak replaces the summary and key frames (§6.4)
                ev["summary"] = obs.get("summary") or ev["summary"]
                if obs["category"] == ev["category"]:
                    ev["subtype"] = obs.get("subtype") or ev["subtype"]
                ev["keyframe_paths"] = keyframes(ev["id"])
                row |= {k: ev[k] for k in ("summary", "subtype", "keyframe_paths")}
            if ev.get("latency_ms") is None and obs["timing"].get("t_vlm_done"):
                ev["latency_ms"] = row["latency_ms"] = round((obs["timing"]["t_vlm_done"] - obs["timing"]["t_capture"]) * 1000)
            self.db.update("events", ev["id"], row)
            self.emit("event_update", ev)
            best = best or ev["id"]
        return best

    def tick(self, now=None, down_since=None):
        """Close rule (§5a step 10, D43). down_since: {camera: time it went reconnecting/down} for cameras that are down.
        Also expires down_guard verifications that never got their re-look (the alert simply stands)."""
        now, down_since = now or time.time(), down_since or {}
        with self.lock:
            for cam in [k for k, h in self.pending.items() if now >= h["deadline"]]:
                self.pending.pop(cam); self.new_holds.discard(cam)
                self.held_log.append((cam, "verify_expired", now))
        with self.lock:
            done = [k for k, ev in self.open.items()
                    if (ev["_nonsupport"] >= E["close_after_obs"] and now - ev["_last_support"] >= E["close_after_s"])
                    or (k[0] in down_since and now - down_since[k[0]] >= E["close_after_s"])]
            closed = [self.open.pop(k) for k in done]
            open_ids = {ev["id"] for ev in self.open.values()}
            for cam in [k for k, h in self.pending.items() if h["eid"] not in open_ids]:
                self.pending.pop(cam); self.new_holds.discard(cam)     # its event closed: nothing left to verify
                self.held_log.append((cam, "verify_moot", now))
        for ev in closed:
            self.close(ev)
        return closed

    def dismiss(self, eid, now=None):
        """Operator marked event eid a false alarm (FR-25): it stops updating and its (camera, category) opens no new
        event for dismiss_hold_s, so the same scene doesn't re-alert a second later. True if it was open."""
        with self.lock:
            k = next((k for k, ev in self.open.items() if ev["id"] == eid), None)
            if k:
                self.open.pop(k)["status"] = "dismissed"
                self.hold[k] = (now or time.time()) + E["dismiss_hold_s"]
        return k is not None

    def close_all(self):
        with self.lock:
            closed, self.open = list(self.open.values()), {}
        for ev in closed:
            self.close(ev)

    def close(self, ev):
        ev["status"] = "closed"
        self.db.update("events", ev["id"], {"status": "closed", "end_ts": ev["end_ts"]})
        self.emit("event_close", ev)


if __name__ == "__main__":
    import tempfile
    from pathlib import Path
    from app.db import DB
    def C(**kw):
        c = dict.fromkeys(CATS, 0.0); c.update(kw); c["normal"] = max(0.0, 1 - sum(kw.values())); return c
    em = EventManager(DB(Path(tempfile.mkdtemp()) / "t.db"))
    obs = lambda: {"category": "fighting", "summary": "Two people shoving.", "track_ids": [1, 2], "timing": {"t_capture": 0, "t_vlm_done": 1.4}}
    # Critical + corroborated by a gate: opens on ONE observation.
    op, _ = em.decide("cam1", C(fighting=0.8), None, {"fighting"}, ts=100, t_ref=99.5, t_alert=100.4)
    assert [e["category"] for e in op] == ["fighting"] and op[0]["time_to_alert_ms"] == 900
    assert em.finish("cam1", obs(), op, lambda i: [f"k{i}"]) == op[0]["id"] and op[0]["summary"] == "Two people shoving."
    # Same confidence without a gate (cam2): no alert on one observation; the window opens it on the second.
    assert em.decide("cam2", C(fighting=0.8), None, set(), 100, 100)[0] == []
    assert [e["category"] for e in em.decide("cam2", C(fighting=0.6), None, set(), 103, 103)[0]] == ["fighting"]
    # High category, uncorroborated, 0.9 once -> no alert (property damage needs 2 observations).
    assert em.decide("cam3", C(property_damage=0.9), "breakage", set(), 100, 100)[0] == []
    # Ungated category after a normal observation: 0.0, 0.83, 0.73 (mean 0.52) opens at 0.50 (D77); 0.0, 0.40, 0.73 doesn't.
    em.decide("cam5", C(), None, set(), 100, 100); em.decide("cam5", C(property_damage=0.83), None, set(), 103, 103)
    assert [e["category"] for e in em.decide("cam5", C(property_damage=0.73), None, set(), 106, 106)[0]] == ["property_damage"]
    em.decide("cam6", C(), None, set(), 100, 100); em.decide("cam6", C(property_damage=0.40), None, set(), 103, 103)
    assert em.decide("cam6", C(property_damage=0.73), None, set(), 106, 106)[0] == []
    # suspicious_activity: loitering is medium (needs 0.85 + gate), weapon is critical but still needs corroboration.
    assert em.decide("cam4", C(suspicious_activity=0.8), "loitering", set(), 100, 100)[0] == []
    # Close rule: 2 non-supporting observations, but only 4 s since support -> stays open; at 8 s -> closes.
    em.decide("cam1", C(), None, set(), 102, 102); em.decide("cam1", C(), None, set(), 104, 104)
    assert em.tick(now=104) == [] and em.is_open("cam1", "fighting")
    assert [e["category"] for e in em.tick(now=108.1)] == ["fighting"] and not em.is_open("cam1", "fighting")
    # Starved camera (no observations for 30 s) keeps its event; a camera down for 8 s closes it.
    assert em.tick(now=140) == [] and em.is_open("cam2", "fighting")
    assert [e["camera_id"] for e in em.tick(now=150, down_since={"cam2": 141})] == ["cam2"]
    # Operator false alarm (FR-25): the event leaves the open set and the same category is held on that camera.
    op, _ = em.decide("cam7", C(fighting=0.8), None, {"fighting"}, 200, 200)
    assert em.dismiss(op[0]["id"], now=200) and not em.is_open("cam7", "fighting") and not em.dismiss(op[0]["id"])
    assert em.decide("cam7", C(fighting=0.9), None, {"fighting"}, 230, 230)[0] == []
    assert [e["category"] for e in em.decide("cam7", C(fighting=0.9), None, {"fighting"}, 200 + E["dismiss_hold_s"] + 1, 0)[0]] == ["fighting"]
    rows = em.db.rows("SELECT camera_id, category, status, summary, keyframe_paths FROM events ORDER BY id")
    assert rows[0] == {"camera_id": "cam1", "category": "fighting", "status": "closed", "summary": "Two people shoving.",
                       "keyframe_paths": [f"k{rows and 1}"]}, rows[0]
    print("events self-check ok")
