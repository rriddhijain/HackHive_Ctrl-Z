"""WhatsApp alerts (D90): critical and high-severity alerts sent to the team's phone through Meta's WhatsApp Cloud API.

Two messages per incident:
  1. the alert, the moment the event opens: what and where, severity, confidence, time, how fast it was raised
     (onset -> alert on a labelled clip, else trigger -> alert), a suggested action and the event id;
  2. about a second later, once the model has written them (whatsapp.snapshot): the event's key frame, captioned with
     the model's one-line summary and its top-3 reading.

Opt-in: idle unless WHATSAPP_TOKEN, WHATSAPP_PHONE_ID and WHATSAPP_TO are set in the environment (never in
config.yaml or git), so the system runs fully offline without them. Detection stays on this machine; what leaves it is
the alert text and, with whatsapp.snapshot, one still frame and the summary. Never video.

Never on the alert path: alert() and details() only filter and put on a queue. One worker thread makes the HTTPS
calls (5 s timeout, 10 s for an image upload); a failure (no internet, an expired token) is printed and counted, never
raised, and an image that fails to upload goes out as its caption.

  WHATSAPP_TOKEN     access token (Meta app > WhatsApp > "Try it out" lasts 24 h; a system user's token can be permanent)
  WHATSAPP_PHONE_ID  "Phone number ID" of the sending number (same page)
  WHATSAPP_TO        recipients with country code, comma-separated: +919812345678

WhatsApp's rules (Meta docs): free text reaches a phone only within 24 h of that phone's last message to the sending
number (send it "hi" on the day); Meta's test number sends only to recipients added and verified on that page.

  uv run python -m app.whatsapp          self-check with a fake endpoint (no internet, no keys)
  uv run python -m app.whatsapp --test   one real test message to every WHATSAPP_TO phone (needs the keys + internet)
"""
import os
import queue
import sys
import threading
import time

from app.config import CFG, ROOT

C = CFG.get("whatsapp") or {}
API = "https://graph.facebook.com/v25.0"
NAME = {"fire_smoke": "FIRE / SMOKE", "fighting": "FIGHT", "person_down": "PERSON DOWN", "crowd_incident": "CROWD INCIDENT",
        "property_damage": "PROPERTY DAMAGE", "suspicious_activity": "SUSPICIOUS ACTIVITY", "tailgating": "TAILGATING",
        "normal": "NORMAL"}
ICON = {"fire_smoke": "🔥", "fighting": "🚨", "person_down": "🚑", "crowd_incident": "👥", "property_damage": "⚠️",
        "suspicious_activity": "👀", "tailgating": "🚪"}
ACTION = {"fire_smoke": "check the camera, raise the fire alarm and evacuate; fire brigade 101 or 112",   # Indian numbers
          "fighting": "send security to {cam} now; police 112 if anyone is hurt or armed",
          "person_down": "send someone to {cam} to check on them; ambulance 108 if they don't respond",
          "crowd_incident": "open exits and stop entry near {cam}; send staff to manage the crowd",
          "property_damage": "send security to {cam} and keep the footage as evidence",
          "weapon": "do not approach; call police 112 and keep people away from {cam}",   # suspicious_activity subtypes
          "theft": "send security to {cam} and keep the footage as evidence",
          "trespass": "send security to {cam} to check for an intruder",
          "tailgating": "check who came through at {cam}"}
HINT = {190: "the access token expired or is wrong: generate a new one on the app's WhatsApp page",
        131030: "this phone isn't an allowed recipient: add and verify it on the app's WhatsApp page",
        131047: "outside WhatsApp's 24 h window: send any message from this phone to the sending number"}


def ist(ts):
    return time.strftime("%H:%M:%S", time.gmtime(ts + 5.5 * 3600)) + " IST"


def alert_text(ev, o2a_ms=None):
    cat, cam, t2a = ev["category"], ev.get("camera_name") or ev["camera_id"], ev.get("time_to_alert_ms")
    act = ACTION.get(ev.get("subtype")) or ACTION.get(cat) or "check {cam}"
    fast = (f"⏱ Raised {o2a_ms / 1000:.1f} s after the incident began" if o2a_ms is not None else
            f"⏱ Raised {t2a / 1000:.1f} s after the AI was triggered" if t2a is not None else None)
    lines = [f"{ICON.get(cat, '⚠️')} *{NAME.get(cat, cat.upper())}*" + (f" ({ev['subtype']})" if ev.get("subtype") else "")
             + f" · {cam}",
             f"*{(ev.get('severity') or 'alert').capitalize()}* · {round(100 * ev['peak_confidence'])}% confidence · "
             f"{ist(ev.get('_t_alert') or time.time())}",
             fast, f"👉 Suggested: {act.format(cam=cam)}.",
             f"_HackHive event #{ev['id']} · detected on this laptop, no cloud AI_"]
    return "\n".join(x for x in lines if x)


def details_text(ev):
    read = " · ".join(f"{NAME.get(k, k).lower()} {round(100 * p)}%" for k, p in ev.get("_probs") or [])
    lines = [f"📷 *Event #{ev['id']}*: what the camera saw at {ev.get('camera_name') or ev['camera_id']}",
             f"_“{ev['summary'].strip()}”_" if ev.get("summary") else None,
             f"AI's read: {read}" if read else None]
    return "\n".join(x for x in lines if x)


def reason(r):
    try:
        e = r.json()["error"]
        return f"HTTP {r.status_code}: {e.get('message')}" + (f" ({HINT[e['code']]})" if e.get("code") in HINT else "")
    except Exception:
        return f"HTTP {r.status_code}"


class WhatsApp:
    def __init__(self, env=None, post=None, cfg=None):
        """env: os.environ (tests pass a dict); post: httpx.post (tests pass a fake); cfg: config.yaml's whatsapp block."""
        env = os.environ if env is None else env
        self.cfg = C if cfg is None else cfg
        self.token, self.phone_id = env.get("WHATSAPP_TOKEN"), env.get("WHATSAPP_PHONE_ID")
        self.to = [d for d in ("".join(filter(str.isdigit, n)) for n in (env.get("WHATSAPP_TO") or "").split(",")) if d]
        self.post, self.q, self.last, self.pending = post, queue.Queue(maxsize=50), {}, {}
        self.state = {"sent": 0, "failed": 0, "dropped": 0, "last_error": None}

    def configured(self):
        return bool(self.cfg.get("enabled", True) and self.token and self.phone_id and self.to)

    def start(self):
        threading.Thread(target=self.run, daemon=True, name="whatsapp").start()
        return self

    def alert(self, ev, o2a_ms=None):
        """Pipeline thread, right after an event opens: never blocks, never raises."""
        try:
            if ev.get("severity") not in self.cfg.get("severities", ["critical", "high"]):
                return False
            key, now = (ev["camera_id"], ev["category"]), time.time()
            if now - self.last.get(key, 0.0) < self.cfg.get("cooldown_s", 60):
                return False
            self.q.put_nowait(("text", alert_text(ev, o2a_ms)))
            self.last[key] = now
            if self.cfg.get("snapshot", True):
                self.pending = {e: t for e, t in self.pending.items() if now - t < 300}   # a follow-up that never came
                self.pending[ev["id"]] = now
            return True
        except queue.Full:
            self.state["dropped"] += 1
        except Exception as e:
            print(f"[whatsapp] skipped: {e!r}", flush=True)
        return False

    def details(self, ev):
        """Pipeline thread, on event_update: the first update of an alerted event that carries its key frame queues
        the photo with the summary, once. Never blocks, never raises."""
        try:
            if not ev.get("keyframe_paths") or self.pending.pop(ev.get("id"), None) is None:
                return False
            self.q.put_nowait(("image", str(ROOT / ev["keyframe_paths"][0]), details_text(ev)))
            return True
        except queue.Full:
            self.state["dropped"] += 1
        except Exception as e:
            print(f"[whatsapp] skipped: {e!r}", flush=True)
        return False

    def http(self):
        if self.post is None:
            import httpx
            self.post = httpx.post
        return self.post

    def upload(self, path):
        """The key frame -> a Cloud API media id, or None (then the caption goes out as text)."""
        try:
            with open(path, "rb") as fh:
                r = self.http()(f"{API}/{self.phone_id}/media", headers={"Authorization": f"Bearer {self.token}"},
                                data={"messaging_product": "whatsapp", "type": "image/jpeg"},
                                files={"file": ("keyframe.jpg", fh.read(), "image/jpeg")}, timeout=10)
            if 200 <= r.status_code < 300:
                return r.json()["id"]
            err = reason(r)
        except Exception as e:
            err = type(e).__name__
        print(f"[whatsapp] key frame upload FAILED {err}: sending the caption only", flush=True)
        return None

    def send(self, to, msg):
        """msg: {"type": "text", "text": {...}} or {"type": "image", "image": {...}}."""
        t0 = time.time()
        try:
            r = self.http()(f"{API}/{self.phone_id}/messages", headers={"Authorization": f"Bearer {self.token}"}, timeout=5,
                            json={"messaging_product": "whatsapp", "recipient_type": "individual", "to": to, **msg})
            err = None if 200 <= r.status_code < 300 else reason(r)
        except Exception as e:                          # offline, DNS, timeout
            err = type(e).__name__
        self.state["sent" if err is None else "failed"] += 1
        self.state["last_error"] = err or self.state["last_error"]
        print(f"[whatsapp] …{to[-4:]}: {msg['type']} {'sent' if err is None else 'FAILED ' + err} in "
              f"{round((time.time() - t0) * 1000)} ms", flush=True)
        return err is None

    def run(self):
        while True:
            item = self.q.get()
            try:
                if item[0] == "text":
                    msg = {"type": "text", "text": {"body": item[1]}}
                else:
                    media = self.upload(item[1])
                    msg = ({"type": "image", "image": {"id": media, "caption": item[2]}} if media
                           else {"type": "text", "text": {"body": item[2]}})
                for to in self.to:
                    self.send(to, msg)
            except Exception as e:                      # the worker never dies
                print(f"[whatsapp] skipped: {e!r}", flush=True)


def selfcheck():
    """Fake Cloud API endpoint, no internet: idle without keys, severity filter, cooldown, both messages' content and
    order, the key frame once per alerted event, upload failure -> caption as text, a queue put only (a dead network
    can't block the caller), failures counted and never raised, Meta's errors explained."""
    import tempfile

    class R:
        def __init__(self, code, body=None):
            self.status_code, self.body = code, body or {}

        def json(self):
            return self.body
    calls, media_ok = [], [True]

    def fake_post(url, **kw):
        calls.append((url, kw))
        if url.endswith("/media"):
            return R(200, {"id": "m1"}) if media_ok[0] else R(400, {"error": {"message": "bad image", "code": 100}})
        return R(200, {"messages": [{"id": "wamid.test"}]})

    def wait(n):
        t0 = time.time()
        while len(calls) < n and time.time() - t0 < 3:
            time.sleep(0.02)
        time.sleep(0.05)
        assert len(calls) == n, [c[0] for c in calls]
    frame = os.path.join(tempfile.mkdtemp(), "41_0.jpg")
    open(frame, "wb").write(b"\xff\xd8 fake jpeg")
    keys = {"WHATSAPP_TOKEN": "tok", "WHATSAPP_PHONE_ID": "123", "WHATSAPP_TO": "+91 98000 00001"}
    cfg = {"enabled": True, "severities": ["critical", "high"], "cooldown_s": 60, "snapshot": True}
    assert not WhatsApp(env={}, cfg=cfg).configured(), "no keys = idle"
    assert not WhatsApp(env=keys, cfg=dict(cfg, enabled=False)).configured(), "config can switch it off"
    w = WhatsApp(env=keys, post=fake_post, cfg=cfg).start()
    assert w.configured() and w.to == ["919800000001"], w.to
    ev = {"id": 41, "camera_id": "cam1", "camera_name": "Lobby", "category": "fighting", "subtype": None, "severity": "critical",
          "peak_confidence": 0.934, "_t_alert": time.time(), "time_to_alert_ms": 1300,
          "_probs": [("fighting", 0.934), ("person_down", 0.04), ("normal", 0.02)], "keyframe_paths": [], "summary": None}
    assert w.alert(ev, o2a_ms=2400)
    assert not w.alert(dict(ev, id=42)), "cooldown per camera + category"
    assert not w.alert(dict(ev, id=43, camera_id="cam2", severity="medium")), "severity filter"
    assert not w.details(ev), "no key frame yet: wait for the update that has it"
    upd = dict(ev, summary=" Two men are shoving each other near the door. ", keyframe_paths=[frame])
    assert w.details(upd) and not w.details(upd), "the key frame goes out once"
    assert not w.details(dict(upd, id=43)), "never for an event that wasn't alerted"
    wait(3)                                                 # alert text, then the upload, then the photo
    (u1, k1), (u2, k2), (u3, k3) = calls
    assert u1 == f"{API}/123/messages" and k1["headers"] == {"Authorization": "Bearer tok"} and k1["json"]["to"] == "919800000001"
    body = k1["json"]["text"]["body"]
    for s in ("🚨 *FIGHT* · Lobby", "*Critical* · 93% confidence", "⏱ Raised 2.4 s after the incident began",
              "👉 Suggested: send security to Lobby now; police 112", "event #41"):
        assert s in body, (s, body)
    assert u2 == f"{API}/123/media" and k2["files"]["file"][2] == "image/jpeg" and k2["data"]["messaging_product"] == "whatsapp"
    cap = k3["json"]["image"]["caption"]
    assert k3["json"]["type"] == "image" and k3["json"]["image"]["id"] == "m1", k3
    assert "📷 *Event #41*: what the camera saw at Lobby" in cap and "_“Two men are shoving each other near the door.”_" in cap
    assert "AI's read: fight 93% · person down 4% · normal 2%" in cap, cap
    assert "⏱ Raised 1.3 s after the AI was triggered" in alert_text(ev), "no labelled onset: trigger -> alert"
    assert "fire brigade 101" in alert_text(dict(ev, category="fire_smoke", subtype="fire"))
    assert "do not approach" in alert_text(dict(ev, category="suspicious_activity", subtype="weapon"))
    media_ok[0] = False                                     # upload fails: the caption still goes out, as text
    fire = dict(ev, id=50, camera_id="cam3", category="fire_smoke", subtype="smoke")
    assert w.alert(fire) and w.details(dict(fire, summary="Smoke rising from a bin.", keyframe_paths=[frame]))
    wait(6)
    assert calls[5][1]["json"]["type"] == "text" and "Smoke rising from a bin." in calls[5][1]["json"]["text"]["body"]
    off = WhatsApp(env=keys, post=fake_post, cfg=dict(cfg, snapshot=False))
    assert off.alert(dict(ev, id=60)) and not off.details(dict(upd, id=60)), "snapshot off: the alert text only"
    idle = WhatsApp(env=keys, post=fake_post, cfg=cfg)      # worker not started: alert() is only a queue put
    t0 = time.time()
    for i in range(80):
        idle.alert(dict(ev, camera_id=f"x{i}"))
    caller_ms = (time.time() - t0) * 1000
    assert caller_ms < 50 and idle.q.qsize() == 50 and idle.state["dropped"] == 30, (caller_ms, idle.state)

    def down(url, **kw):
        raise OSError("network unreachable")
    f = WhatsApp(env=keys, post=down, cfg=cfg)
    assert not f.send("919800000001", {"type": "text", "text": {"body": "x"}}) and f.state["last_error"] == "OSError"
    e = WhatsApp(env=keys, post=lambda url, **kw: R(401, {"error": {"message": "Session has expired", "code": 190}}), cfg=cfg)
    assert not e.send("919800000001", {"type": "text", "text": {"body": "x"}})
    assert e.state["last_error"] == f"HTTP 401: Session has expired ({HINT[190]})", e.state
    print(f"whatsapp self-check ok: idle without keys, filters, cooldown, alert text, key frame + summary once, upload "
          f"failure -> caption, 80 alerts queued in {caller_ms:.1f} ms with no network call, failures counted not raised")


def main():
    if "--test" not in sys.argv:
        return selfcheck()
    w = WhatsApp()
    if not (w.token and w.phone_id and w.to):
        raise SystemExit("set WHATSAPP_TOKEN, WHATSAPP_PHONE_ID and WHATSAPP_TO first (see `python -m app.whatsapp` docs)")
    ok = [w.send(to, {"type": "text", "text": {"body": "*✅ HackHive test*: WhatsApp alerts are working. No incident."}})
          for to in w.to]
    if all(ok):                                         # the API accepts first; delivery is only reported to a webhook
        print("[whatsapp] accepted. Nothing on the phone within ~10 s? Send any message from that phone to the sending "
              "number (WhatsApp's 24 h window) and run this again.", flush=True)
    raise SystemExit(0 if all(ok) else 1)


if __name__ == "__main__":
    main()
