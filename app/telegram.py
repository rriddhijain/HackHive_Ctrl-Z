"""Telegram alerts (D91, replacing D90's WhatsApp): critical and high-severity alerts sent to the team's phone through
Telegram's Bot API.

Two messages per incident:
  1. the alert, the moment the event opens: what and where, severity, confidence, time, how fast it was raised
     (onset -> alert on a labelled clip, else trigger -> alert), a suggested action and the event id;
  2. about a second later, once the model has written them (telegram.snapshot): the event's key frame, captioned with
     the model's one-line summary and its top-3 reading.

Opt-in: idle unless TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are set in the environment (never in config.yaml or git),
so the system runs fully offline without them. Detection stays on this machine; what leaves it is the alert text and,
with telegram.snapshot, one still frame and the summary. Never video.

Never on the alert path: alert() and details() only filter and put on a queue. One worker thread makes the HTTPS
calls (5 s timeout, 15 s for a photo); a failure (no internet, a wrong token) is printed and counted, never raised, and
a photo that fails goes out as its caption. Unlike Meta's WhatsApp API, Telegram answers 200 only once the message is
in the chat, so "sent" means the phone will show it.

  TELEGRAM_BOT_TOKEN  from @BotFather (/newbot)
  TELEGRAM_CHAT_ID    who receives, comma-separated chat ids; tap Start on the bot, then `--chat-id` lists them

  uv run python -m app.telegram            self-check with a fake endpoint (no internet, no keys)
  uv run python -m app.telegram --chat-id  the chats that tapped Start on the bot (needs TELEGRAM_BOT_TOKEN)
  uv run python -m app.telegram --test     one real test message to every TELEGRAM_CHAT_ID (needs the keys + internet)
"""
import html
import os
import queue
import sys
import threading
import time

from app.config import CFG, ROOT

C = CFG.get("telegram") or {}
API = "https://api.telegram.org"
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
HINT = {401: "the bot token is wrong: copy it again from @BotFather",
        403: "this chat hasn't tapped Start on the bot, or blocked it: tap Start in Telegram",
        "chat not found": "wrong TELEGRAM_CHAT_ID: tap Start on the bot, then run `python -m app.telegram --chat-id`"}


def esc(s):
    return html.escape(str(s), quote=False)


def ist(ts):
    return time.strftime("%H:%M:%S", time.gmtime(ts + 5.5 * 3600)) + " IST"


def alert_text(ev, o2a_ms=None):
    cat, cam, t2a = ev["category"], esc(ev.get("camera_name") or ev["camera_id"]), ev.get("time_to_alert_ms")
    act = ACTION.get(ev.get("subtype")) or ACTION.get(cat) or "check {cam}"
    fast = (f"⏱ Raised {o2a_ms / 1000:.1f} s after the incident began" if o2a_ms is not None else
            f"⏱ Raised {t2a / 1000:.1f} s after the AI was triggered" if t2a is not None else None)
    lines = [f"{ICON.get(cat, '⚠️')} <b>{esc(NAME.get(cat, cat.upper()))}</b>"
             + (f" ({esc(ev['subtype'])})" if ev.get("subtype") else "") + f" · {cam}",
             f"<b>{esc((ev.get('severity') or 'alert').capitalize())}</b> · {round(100 * ev['peak_confidence'])}% confidence · "
             f"{ist(ev.get('_t_alert') or time.time())}",
             fast, f"👉 Suggested: {act.format(cam=cam)}.",
             f"<i>HackHive event #{ev['id']} · detected on this laptop, no cloud AI</i>"]
    return "\n".join(x for x in lines if x)


def details_text(ev):
    read = " · ".join(f"{NAME.get(k, k).lower()} {round(100 * p)}%" for k, p in ev.get("_probs") or [])
    lines = [f"📷 <b>Event #{ev['id']}</b>: what the camera saw at {esc(ev.get('camera_name') or ev['camera_id'])}",
             f"<i>“{esc(ev['summary'].strip()[:600])}”</i>" if ev.get("summary") else None,   # captions stop at 1024
             f"AI's read: {esc(read)}" if read else None]
    return "\n".join(x for x in lines if x)


def reason(r):
    try:
        d = r.json().get("description") or ""
    except Exception:
        d = ""
    hint = HINT.get(r.status_code) or next((h for k, h in HINT.items() if isinstance(k, str) and k in d.lower()), None)
    return f"HTTP {r.status_code}" + (f": {d}" if d else "") + (f" ({hint})" if hint else "")


class Telegram:
    def __init__(self, env=None, post=None, cfg=None):
        """env: os.environ (tests pass a dict); post: httpx.post (tests pass a fake); cfg: config.yaml's telegram block."""
        env = os.environ if env is None else env
        self.cfg = C if cfg is None else cfg
        self.token = env.get("TELEGRAM_BOT_TOKEN")
        self.to = [c.strip() for c in (env.get("TELEGRAM_CHAT_ID") or "").split(",") if c.strip()]
        self.post, self.q, self.last, self.pending = post, queue.Queue(maxsize=50), {}, {}
        self.state = {"sent": 0, "failed": 0, "dropped": 0, "last_error": None}

    def configured(self):
        return bool(self.cfg.get("enabled", True) and self.token and self.to)

    def start(self):
        threading.Thread(target=self.run, daemon=True, name="telegram").start()
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
            print(f"[telegram] skipped: {e!r}", flush=True)
        return False

    def details(self, ev):
        """Pipeline thread, on event_update: the first update of an alerted event that carries its key frame queues
        the photo with the summary, once. Never blocks, never raises."""
        try:
            if not ev.get("keyframe_paths") or self.pending.pop(ev.get("id"), None) is None:
                return False
            self.q.put_nowait(("photo", str(ROOT / ev["keyframe_paths"][0]), details_text(ev)))
            return True
        except queue.Full:
            self.state["dropped"] += 1
        except Exception as e:
            print(f"[telegram] skipped: {e!r}", flush=True)
        return False

    def http(self):
        if self.post is None:
            import httpx
            self.post = httpx.post
        return self.post

    def send(self, chat, text=None, photo=None, caption=None):
        """One Bot API call: sendMessage(text) or sendPhoto(photo bytes, caption). The token sits in the URL, so errors
        print only the exception's type, never its message."""
        t0 = time.time()
        try:
            if photo is None:
                r = self.http()(f"{API}/bot{self.token}/sendMessage", timeout=5,
                                json={"chat_id": chat, "text": text, "parse_mode": "HTML"})
            else:
                r = self.http()(f"{API}/bot{self.token}/sendPhoto", timeout=15,
                                data={"chat_id": chat, "caption": caption, "parse_mode": "HTML"},
                                files={"photo": ("keyframe.jpg", photo, "image/jpeg")})
            err = None if r.status_code == 200 else reason(r)
        except Exception as e:                          # offline, DNS, timeout
            err = type(e).__name__
        self.state["sent" if err is None else "failed"] += 1
        self.state["last_error"] = err or self.state["last_error"]
        print(f"[telegram] chat …{str(chat)[-4:]}: {'text' if photo is None else 'photo'} "
              f"{'sent' if err is None else 'FAILED ' + err} in {round((time.time() - t0) * 1000)} ms", flush=True)
        return err is None

    def run(self):
        while True:
            item = self.q.get()
            try:
                if item[0] == "text":
                    for chat in self.to:
                        self.send(chat, text=item[1])
                    continue
                try:
                    with open(item[1], "rb") as fh:
                        photo = fh.read()
                except OSError:
                    photo = None
                for chat in self.to:
                    if not (photo and self.send(chat, photo=photo, caption=item[2])):
                        self.send(chat, text=item[2])  # no key frame, or the photo failed: the caption still goes out
            except Exception as e:                      # the worker never dies
                print(f"[telegram] skipped: {e!r}", flush=True)


def chat_ids(token, get=None):
    """{chat id: name} of every chat that messaged the bot in the last 24 h (tapping Start sends /start)."""
    if get is None:
        import httpx
        get = httpx.get
    out = {}
    for u in get(f"{API}/bot{token}/getUpdates", timeout=10).json().get("result", []):
        c = (u.get("message") or u.get("my_chat_member") or {}).get("chat") or {}
        if c.get("id"):
            out[c["id"]] = " ".join(x for x in (c.get("first_name"), c.get("last_name"), c.get("title")) if x)
    return out


def selfcheck():
    """Fake Bot API endpoint, no internet: idle without keys, severity filter, cooldown, both messages' content and
    order, HTML escaping, the key frame once per alerted event, photo failure -> caption as text, a queue put only (a
    dead network can't block the caller), failures counted and never raised, Telegram's errors explained."""
    import tempfile

    class R:
        def __init__(self, code, body=None):
            self.status_code, self.body = code, body or {}

        def json(self):
            return self.body
    calls, photo_ok = [], [True]

    def fake_post(url, **kw):
        calls.append((url, kw))
        if url.endswith("/sendPhoto") and not photo_ok[0]:
            return R(400, {"ok": False, "description": "Bad Request: IMAGE_PROCESS_FAILED"})
        return R(200, {"ok": True, "result": {"message_id": len(calls)}})

    def wait(n):
        t0 = time.time()
        while len(calls) < n and time.time() - t0 < 3:
            time.sleep(0.02)
        time.sleep(0.05)
        assert len(calls) == n, [c[0] for c in calls]
    frame = os.path.join(tempfile.mkdtemp(), "41_0.jpg")
    open(frame, "wb").write(b"\xff\xd8 fake jpeg")
    keys = {"TELEGRAM_BOT_TOKEN": "123:tok", "TELEGRAM_CHAT_ID": " 5551234 "}
    cfg = {"enabled": True, "severities": ["critical", "high"], "cooldown_s": 60, "snapshot": True}
    assert not Telegram(env={}, cfg=cfg).configured(), "no keys = idle"
    assert not Telegram(env=keys, cfg=dict(cfg, enabled=False)).configured(), "config can switch it off"
    t = Telegram(env=keys, post=fake_post, cfg=cfg).start()
    assert t.configured() and t.to == ["5551234"], t.to
    ev = {"id": 41, "camera_id": "cam1", "camera_name": "Lobby <A&B>", "category": "fighting", "subtype": None,
          "severity": "critical", "peak_confidence": 0.934, "_t_alert": time.time(), "time_to_alert_ms": 1300,
          "_probs": [("fighting", 0.934), ("person_down", 0.04), ("normal", 0.02)], "keyframe_paths": [], "summary": None}
    assert t.alert(ev, o2a_ms=2400)
    assert not t.alert(dict(ev, id=42)), "cooldown per camera + category"
    assert not t.alert(dict(ev, id=43, camera_id="cam2", severity="medium")), "severity filter"
    assert not t.details(ev), "no key frame yet: wait for the update that has it"
    upd = dict(ev, summary=" Two men <shoving> near the door & a bin. ", keyframe_paths=[frame])
    assert t.details(upd) and not t.details(upd), "the key frame goes out once"
    assert not t.details(dict(upd, id=43)), "never for an event that wasn't alerted"
    wait(2)                                                 # alert text, then the photo
    (u1, k1), (u2, k2) = calls
    assert u1 == f"{API}/bot123:tok/sendMessage" and k1["json"]["chat_id"] == "5551234" and k1["json"]["parse_mode"] == "HTML"
    body = k1["json"]["text"]
    for s in ("🚨 <b>FIGHT</b> · Lobby &lt;A&amp;B&gt;", "<b>Critical</b> · 93% confidence", "⏱ Raised 2.4 s after the incident began",
              "👉 Suggested: send security to Lobby &lt;A&amp;B&gt; now; police 112", "event #41"):
        assert s in body, (s, body)
    assert u2 == f"{API}/bot123:tok/sendPhoto" and k2["files"]["photo"] == ("keyframe.jpg", b"\xff\xd8 fake jpeg", "image/jpeg")
    cap = k2["data"]["caption"]
    assert k2["data"]["chat_id"] == "5551234" and k2["data"]["parse_mode"] == "HTML", k2
    assert "📷 <b>Event #41</b>: what the camera saw at Lobby &lt;A&amp;B&gt;" in cap, cap
    assert "<i>“Two men &lt;shoving&gt; near the door &amp; a bin.”</i>" in cap, cap
    assert "AI's read: fight 93% · person down 4% · normal 2%" in cap, cap
    assert "⏱ Raised 1.3 s after the AI was triggered" in alert_text(ev), "no labelled onset: trigger -> alert"
    assert "fire brigade 101" in alert_text(dict(ev, category="fire_smoke", subtype="fire"))
    assert "do not approach" in alert_text(dict(ev, category="suspicious_activity", subtype="weapon"))
    photo_ok[0] = False                                     # the photo fails: the caption still goes out, as text
    fire = dict(ev, id=50, camera_id="cam3", category="fire_smoke", subtype="smoke")
    assert t.alert(fire) and t.details(dict(fire, summary="Smoke rising from a bin.", keyframe_paths=[frame]))
    wait(5)                                                 # text, failed photo, caption as text
    assert calls[3][0].endswith("/sendPhoto") and calls[4][0].endswith("/sendMessage")
    assert "Smoke rising from a bin." in calls[4][1]["json"]["text"] and t.state["failed"] == 1, t.state
    assert "IMAGE_PROCESS_FAILED" in t.state["last_error"], t.state
    off = Telegram(env=keys, post=fake_post, cfg=dict(cfg, snapshot=False))
    assert off.alert(dict(ev, id=60)) and not off.details(dict(upd, id=60)), "snapshot off: the alert text only"
    idle = Telegram(env=keys, post=fake_post, cfg=cfg)      # worker not started: alert() is only a queue put
    t0 = time.time()
    for i in range(80):
        idle.alert(dict(ev, camera_id=f"x{i}"))
    caller_ms = (time.time() - t0) * 1000
    assert caller_ms < 50 and idle.q.qsize() == 50 and idle.state["dropped"] == 30, (caller_ms, idle.state)

    def down(url, **kw):
        raise OSError(f"network unreachable: {url}")
    f = Telegram(env=keys, post=down, cfg=cfg)
    assert not f.send("5551234", text="x") and f.state["last_error"] == "OSError", "type only: the URL holds the token"
    e = Telegram(env=keys, post=lambda url, **kw: R(401, {"ok": False, "description": "Unauthorized"}), cfg=cfg)
    assert not e.send("5551234", text="x") and e.state["last_error"] == f"HTTP 401: Unauthorized ({HINT[401]})", e.state
    n = Telegram(env=keys, post=lambda url, **kw: R(400, {"ok": False, "description": "Bad Request: chat not found"}), cfg=cfg)
    assert not n.send("5551234", text="x") and HINT["chat not found"] in n.state["last_error"], n.state

    class G(R):
        pass
    ups = {"ok": True, "result": [{"update_id": 1, "message": {"chat": {"id": 777, "first_name": "Shivansh"}, "text": "/start"}}]}
    assert chat_ids("123:tok", get=lambda url, **kw: G(200, ups)) == {777: "Shivansh"}
    print(f"telegram self-check ok: idle without keys, filters, cooldown, alert text, HTML escaped, key frame + summary "
          f"once, photo failure -> caption, 80 alerts queued in {caller_ms:.1f} ms with no network call, failures "
          f"counted not raised, chat ids from getUpdates")


def main():
    if "--chat-id" in sys.argv:
        token = os.environ.get("TELEGRAM_BOT_TOKEN") or sys.exit("set TELEGRAM_BOT_TOKEN first")
        found = chat_ids(token)
        for cid, name in found.items():
            print(f"{cid}  {name}")
        sys.exit(0 if found else "no chats yet: open the bot in Telegram and tap Start, then run this again")
    if "--test" not in sys.argv:
        return selfcheck()
    t = Telegram()
    if not (t.token and t.to):
        sys.exit("set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID first (see `python -m app.telegram` docs)")
    ok = [t.send(c, text="✅ <b>HackHive test</b>: Telegram alerts are working. No incident.") for c in t.to]
    sys.exit(0 if all(ok) else 1)


if __name__ == "__main__":
    main()
