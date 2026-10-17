"""WhatsApp alerts (D90): critical and high-severity alerts sent to the team's phone through Meta's WhatsApp Cloud API.

Opt-in: idle unless WHATSAPP_TOKEN, WHATSAPP_PHONE_ID and WHATSAPP_TO are set in the environment (never in
config.yaml or git), so the system runs fully offline without them. Inference stays on this machine; what leaves it is
metadata only: category, camera name, IST time, confidence, event id. Never frames, never the model's summary.

Never on the alert path: alert() checks the severity and a per-camera + category cooldown, then puts the text on a
queue. One worker thread makes the HTTPS calls (5 s timeout); a failure (no internet, an expired token) is printed and
counted, never raised.

  WHATSAPP_TOKEN     access token (Meta app > WhatsApp > API Setup lasts 24 h; a system user's token can be permanent)
  WHATSAPP_PHONE_ID  "Phone number ID" of the sending number (same page)
  WHATSAPP_TO        recipients with country code, comma-separated: +919812345678

WhatsApp's rules (Meta docs): free text reaches a phone only within 24 h of that phone's last message to the sending
number (send it "hi" on the day); Meta's test number sends only to recipients added and verified on API Setup.

  uv run python -m app.whatsapp          self-check with a fake endpoint (no internet, no keys)
  uv run python -m app.whatsapp --test   one real test message to every WHATSAPP_TO phone (needs the keys + internet)
"""
import os
import queue
import sys
import threading
import time

from app.config import CFG

C = CFG.get("whatsapp") or {}
API = "https://graph.facebook.com/v23.0"
TITLE = {"fire_smoke": "🔥 FIRE / SMOKE", "fighting": "🚨 FIGHT", "person_down": "🚑 PERSON DOWN",
         "crowd_incident": "👥 CROWD INCIDENT", "property_damage": "⚠️ PROPERTY DAMAGE",
         "suspicious_activity": "👀 SUSPICIOUS ACTIVITY", "tailgating": "🚪 TAILGATING"}
HINT = {190: "the access token expired or is wrong: generate a new one on API Setup",
        131030: "this phone isn't an allowed recipient: add and verify it under API Setup > To",
        131047: "outside WhatsApp's 24 h window: send any message from this phone to the sending number"}


def ist(ts):
    return time.strftime("%H:%M:%S", time.gmtime(ts + 5.5 * 3600)) + " IST"


def text(ev):
    sub = f" ({ev['subtype']})" if ev.get("subtype") else ""
    return (f"*{TITLE.get(ev['category'], ev['category'].upper())}*{sub} at {ev.get('camera_name') or ev['camera_id']}\n"
            f"{ist(ev.get('_t_alert') or time.time())} · confidence {round(100 * ev['peak_confidence'])}% · event #{ev['id']}\n"
            "HackHive alert: check the camera before acting.")


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
        self.post, self.q, self.last = post, queue.Queue(maxsize=50), {}
        self.state = {"sent": 0, "failed": 0, "dropped": 0, "last_error": None}

    def configured(self):
        return bool(self.cfg.get("enabled", True) and self.token and self.phone_id and self.to)

    def start(self):
        threading.Thread(target=self.run, daemon=True, name="whatsapp").start()
        return self

    def alert(self, ev):
        """Pipeline thread, right after an event opens: never blocks, never raises."""
        try:
            if ev.get("severity") not in self.cfg.get("severities", ["critical", "high"]):
                return False
            key, now = (ev["camera_id"], ev["category"]), time.time()
            if now - self.last.get(key, 0.0) < self.cfg.get("cooldown_s", 60):
                return False
            self.q.put_nowait(text(ev))
            self.last[key] = now
            return True
        except queue.Full:
            self.state["dropped"] += 1
        except Exception as e:
            print(f"[whatsapp] skipped: {e!r}", flush=True)
        return False

    def send(self, to, body):
        post = self.post
        if post is None:
            import httpx
            post = httpx.post
        t0 = time.time()
        try:
            r = post(f"{API}/{self.phone_id}/messages", headers={"Authorization": f"Bearer {self.token}"}, timeout=5,
                     json={"messaging_product": "whatsapp", "recipient_type": "individual", "to": to, "type": "text",
                           "text": {"body": body}})
            err = None if 200 <= r.status_code < 300 else reason(r)
        except Exception as e:                          # offline, DNS, timeout
            err = type(e).__name__
        self.state["sent" if err is None else "failed"] += 1
        self.state["last_error"] = err or self.state["last_error"]
        print(f"[whatsapp] …{to[-4:]}: {'sent' if err is None else 'FAILED ' + err} in {round((time.time() - t0) * 1000)} ms",
              flush=True)
        return err is None

    def run(self):
        while True:
            body = self.q.get()
            for to in self.to:
                self.send(to, body)


def selfcheck():
    """Fake Cloud API endpoint, no internet: idle without keys, severity filter, cooldown, payload, a queue put only (a
    dead network can't block the caller), failures counted and never raised, Meta's error explained."""
    class R:
        def __init__(self, code, body=None):
            self.status_code, self.body = code, body or {}

        def json(self):
            return self.body
    calls = []

    def fake_post(url, **kw):
        calls.append((url, kw))
        return R(200, {"messages": [{"id": "wamid.test"}]})
    keys = {"WHATSAPP_TOKEN": "tok", "WHATSAPP_PHONE_ID": "123", "WHATSAPP_TO": "+91 98000 00001, +919800000002"}
    cfg = {"enabled": True, "severities": ["critical", "high"], "cooldown_s": 60}
    assert not WhatsApp(env={}, cfg=cfg).configured(), "no keys = idle"
    assert not WhatsApp(env=keys, cfg=dict(cfg, enabled=False)).configured(), "config can switch it off"
    w = WhatsApp(env=keys, post=fake_post, cfg=cfg).start()
    assert w.configured() and w.to == ["919800000001", "919800000002"], w.to
    ev = {"id": 41, "camera_id": "cam1", "camera_name": "Lobby", "category": "fire_smoke", "subtype": "fire",
          "severity": "critical", "peak_confidence": 0.934, "_t_alert": time.time()}
    assert w.alert(ev)
    assert not w.alert(dict(ev, id=42)), "cooldown per camera + category"
    assert not w.alert(dict(ev, camera_id="cam2", severity="medium")), "severity filter"
    assert w.alert(dict(ev, id=43, camera_id="cam2", category="fighting", subtype=None))
    t0 = time.time()
    while len(calls) < 4 and time.time() - t0 < 3:
        time.sleep(0.02)
    assert len(calls) == 4, calls
    url, kw = calls[0]
    assert url == f"{API}/123/messages" and kw["headers"] == {"Authorization": "Bearer tok"}, (url, kw)
    assert [c[1]["json"]["to"] for c in calls] == ["919800000001", "919800000002"] * 2
    body = kw["json"]["text"]["body"]
    assert kw["json"]["type"] == "text" and "*🔥 FIRE / SMOKE* (fire) at Lobby" in body and "93%" in body and "#41" in body, body
    assert "*🚨 FIGHT* at Lobby" in calls[2][1]["json"]["text"]["body"] and "#43" in calls[2][1]["json"]["text"]["body"]
    idle = WhatsApp(env=keys, post=fake_post, cfg=cfg)  # worker not started: alert() is only a queue put
    t0 = time.time()
    for i in range(80):
        idle.alert(dict(ev, camera_id=f"x{i}"))
    caller_ms = (time.time() - t0) * 1000
    assert caller_ms < 50 and idle.q.qsize() == 50 and idle.state["dropped"] == 30, (caller_ms, idle.state)

    def down(url, **kw):
        raise OSError("network unreachable")
    f = WhatsApp(env=keys, post=down, cfg=cfg)
    assert not f.send("919800000001", "x") and f.state == {"sent": 0, "failed": 1, "dropped": 0, "last_error": "OSError"}
    e = WhatsApp(env=keys, post=lambda url, **kw: R(401, {"error": {"message": "Session has expired", "code": 190}}), cfg=cfg)
    assert not e.send("919800000001", "x") and e.state["last_error"] == f"HTTP 401: Session has expired ({HINT[190]})"
    print(f"whatsapp self-check ok: idle without keys, filters, cooldown, payload, 80 alerts queued in {caller_ms:.1f} ms "
          f"with no network call, failures counted not raised")


def main():
    if "--test" not in sys.argv:
        return selfcheck()
    w = WhatsApp()
    if not (w.token and w.phone_id and w.to):
        raise SystemExit("set WHATSAPP_TOKEN, WHATSAPP_PHONE_ID and WHATSAPP_TO first (see `python -m app.whatsapp` docs)")
    ok = [w.send(to, "*✅ HackHive test*: WhatsApp alerts are working. No incident.") for to in w.to]
    if all(ok):                                         # the API accepts first; delivery is only reported to a webhook
        print("[whatsapp] accepted. Nothing on the phone within ~10 s? Send any message from that phone to the sending "
              "number (WhatsApp's 24 h window) and run this again.", flush=True)
    raise SystemExit(0 if all(ok) else 1)


if __name__ == "__main__":
    main()
