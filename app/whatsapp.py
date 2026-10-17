"""WhatsApp alerts (D90): critical and high-severity alerts sent to the team's phones through Twilio's WhatsApp API.

Opt-in: idle unless TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN and WHATSAPP_TO are set in the environment (never in
config.yaml or git), so the system runs fully offline without them. Inference stays on this machine; what leaves it is
metadata only: category, camera name, IST time, confidence, event id. Never frames, never the model's summary.

Never on the alert path: alert() checks the severity and a per-camera + category cooldown, then puts the text on a
queue. One worker thread makes the HTTPS calls (5 s timeout, at most one message every 3 s: the sandbox's limit); a
failure (no internet, a phone that hasn't joined the sandbox) is printed and counted, never raised.

  WHATSAPP_TO     phone numbers with country code, comma-separated: +919812345678,+919876543210
  WHATSAPP_FROM   sender, default whatsapp:+14155238886 (Twilio's shared sandbox number)

Sandbox rules (Twilio docs): each phone first sends "join <your code>" to +1 415 523 8886; free-form messages reach a
phone only within 24 h of its last message to the sandbox (message it again on the day), and a join lapses after 3 days.

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
SANDBOX = "whatsapp:+14155238886"
GAP_S = 3.0                                         # Twilio sandbox: one message every 3 s
TITLE = {"fire_smoke": "🔥 FIRE / SMOKE", "fighting": "🚨 FIGHT", "person_down": "🚑 PERSON DOWN",
         "crowd_incident": "👥 CROWD INCIDENT", "property_damage": "⚠️ PROPERTY DAMAGE",
         "suspicious_activity": "👀 SUSPICIOUS ACTIVITY", "tailgating": "🚪 TAILGATING"}


def ist(ts):
    return time.strftime("%H:%M:%S", time.gmtime(ts + 5.5 * 3600)) + " IST"


def text(ev):
    sub = f" ({ev['subtype']})" if ev.get("subtype") else ""
    return (f"*{TITLE.get(ev['category'], ev['category'].upper())}*{sub} at {ev.get('camera_name') or ev['camera_id']}\n"
            f"{ist(ev.get('_t_alert') or time.time())} · confidence {round(100 * ev['peak_confidence'])}% · event #{ev['id']}\n"
            "HackHive alert: check the camera before acting.")


def reason(r):
    try:
        return f"HTTP {r.status_code}: {r.json().get('message')}"
    except Exception:
        return f"HTTP {r.status_code}"


class WhatsApp:
    def __init__(self, env=None, post=None, cfg=None):
        """env: os.environ (tests pass a dict); post: httpx.post (tests pass a fake); cfg: config.yaml's whatsapp block."""
        env = os.environ if env is None else env
        self.cfg = C if cfg is None else cfg
        self.sid, self.token = env.get("TWILIO_ACCOUNT_SID"), env.get("TWILIO_AUTH_TOKEN")
        self.sender = env.get("WHATSAPP_FROM") or SANDBOX
        self.to = [n.strip() for n in (env.get("WHATSAPP_TO") or "").split(",") if n.strip()]
        self.post, self.gap, self.next_ok = post, GAP_S, 0.0
        self.q, self.last = queue.Queue(maxsize=50), {}
        self.state = {"sent": 0, "failed": 0, "dropped": 0, "last_error": None}

    def configured(self):
        return bool(self.cfg.get("enabled", True) and self.sid and self.token and self.to)

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
            r = post(f"https://api.twilio.com/2010-04-01/Accounts/{self.sid}/Messages.json", auth=(self.sid, self.token),
                     data={"From": self.sender, "To": to if to.startswith("whatsapp:") else "whatsapp:" + to, "Body": body},
                     timeout=5)
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
                time.sleep(max(0.0, self.next_ok - time.time()))
                self.send(to, body)
                self.next_ok = time.time() + self.gap


def selfcheck():
    """Fake Twilio endpoint, no internet: idle without keys, severity filter, cooldown, payload, pacing, a queue put
    only (a dead network can't block the caller), failures counted and never raised."""
    class R:
        def __init__(self, code, msg=None):
            self.status_code, self.msg = code, msg

        def json(self):
            return {"message": self.msg}
    calls = []

    def fake_post(url, **kw):
        calls.append((time.time(), url, kw))
        return R(201)
    keys = {"TWILIO_ACCOUNT_SID": "ACtest", "TWILIO_AUTH_TOKEN": "tok", "WHATSAPP_TO": "+919800000001, +919800000002"}
    cfg = {"enabled": True, "severities": ["critical", "high"], "cooldown_s": 60}
    assert not WhatsApp(env={}, cfg=cfg).configured(), "no keys = idle"
    assert not WhatsApp(env=keys, cfg=dict(cfg, enabled=False)).configured(), "config can switch it off"
    w = WhatsApp(env=keys, post=fake_post, cfg=cfg)
    w.gap = 0.3
    w.start()
    assert w.configured() and w.to == ["+919800000001", "+919800000002"]
    ev = {"id": 41, "camera_id": "cam1", "camera_name": "Lobby", "category": "fire_smoke", "subtype": "fire",
          "severity": "critical", "peak_confidence": 0.934, "_t_alert": time.time()}
    assert w.alert(ev)
    assert not w.alert(dict(ev, id=42)), "cooldown per camera + category"
    assert not w.alert(dict(ev, camera_id="cam2", severity="medium")), "severity filter"
    assert w.alert(dict(ev, id=43, camera_id="cam2", category="fighting", subtype=None))
    t0 = time.time()
    while len(calls) < 4 and time.time() - t0 < 5:
        time.sleep(0.02)
    assert len(calls) == 4, calls
    _, url, kw = calls[0]
    assert url == "https://api.twilio.com/2010-04-01/Accounts/ACtest/Messages.json" and kw["auth"] == ("ACtest", "tok")
    assert [c[2]["data"]["To"] for c in calls] == ["whatsapp:+919800000001", "whatsapp:+919800000002"] * 2
    body = kw["data"]["Body"]
    assert kw["data"]["From"] == SANDBOX and "*🔥 FIRE / SMOKE* (fire) at Lobby" in body and "93%" in body and "#41" in body, body
    assert "*🚨 FIGHT* at Lobby" in calls[2][2]["data"]["Body"] and "#43" in calls[2][2]["data"]["Body"]
    gaps = [b[0] - a[0] for a, b in zip(calls, calls[1:])]
    assert min(gaps) >= 0.29, gaps                  # paced: the sandbox takes one message every 3 s
    idle = WhatsApp(env=keys, post=fake_post, cfg=cfg)  # worker not started: alert() is only a queue put
    t0 = time.time()
    for i in range(80):
        idle.alert(dict(ev, camera_id=f"x{i}"))
    caller_ms = (time.time() - t0) * 1000
    assert caller_ms < 50 and idle.q.qsize() == 50 and idle.state["dropped"] == 30, (caller_ms, idle.state)

    def down(url, **kw):
        raise OSError("network unreachable")
    f = WhatsApp(env=keys, post=down, cfg=cfg)
    assert not f.send("+919800000001", "x") and f.state == {"sent": 0, "failed": 1, "dropped": 0, "last_error": "OSError"}
    e = WhatsApp(env=keys, post=lambda url, **kw: R(400, "not in the sandbox"), cfg=cfg)
    assert not e.send("+919800000001", "x") and e.state["last_error"] == "HTTP 400: not in the sandbox"
    print(f"whatsapp self-check ok: idle without keys, filters, cooldown, payload, paced, 80 alerts queued in "
          f"{caller_ms:.1f} ms with no network call, failures counted not raised")


def main():
    if "--test" not in sys.argv:
        return selfcheck()
    w = WhatsApp()
    if not (w.sid and w.token and w.to):
        raise SystemExit("set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN and WHATSAPP_TO first (see `python -m app.whatsapp` docs)")
    ok = []
    for i, to in enumerate(w.to):
        time.sleep(GAP_S if i else 0)
        ok.append(w.send(to, "*✅ HackHive test*: WhatsApp alerts are working. No incident."))
    raise SystemExit(0 if all(ok) else 1)


if __name__ == "__main__":
    main()
