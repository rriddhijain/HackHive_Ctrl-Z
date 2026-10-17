"""Opt-in remote notifications (D89, proposed): push critical alerts to phones over ntfy and/or Telegram.

  uv run python -m app.notify            self-check with a local fake server (no internet, no keys)
  uv run python -m app.notify --test     send one test message to the configured channels (needs internet)

The system is fully offline without this. It is OFF by default (config.yaml notify.enabled) and can be switched on at
runtime (POST /api/notify {"enabled": true}) once the audience agrees, e.g. "all residents of a building get the fire
alert". What leaves the machine: category, camera name, IST time, confidence, event id. Never frames, never video;
the model's summary only if notify.include_summary is true.

Never on the alert path: emit() calls Notifier.alert(), which only checks a few fields and puts on a bounded queue
(the oldest message is dropped when full). One worker thread does the HTTP calls with a short timeout; failures are
counted, logged and shown in /api/notify, never raised. A per-camera-and-category cooldown stops one incident from
spamming a whole building.

Secrets are environment variables, never config.yaml or git:
  HACKHIVE_NTFY_URL          e.g. https://ntfy.sh/<long-random-topic>   (public ntfy topics are readable by anyone
                             who guesses the name: use a long random topic, or a self-hosted ntfy on the site LAN)
  HACKHIVE_TELEGRAM_TOKEN    bot token from @BotFather
  HACKHIVE_TELEGRAM_CHAT     chat id or @channel the bot posts to (the bot must be an admin of a channel)
"""
import os
import queue
import threading
import time
from collections import deque

from app.config import CFG

C = CFG.get("notify") or {}
LABEL = {"fire_smoke": ("FIRE / SMOKE", "fire"), "fighting": ("FIGHT", "rotating_light"), "person_down": ("PERSON DOWN", "ambulance"),
         "crowd_incident": ("CROWD INCIDENT", "busts_in_silhouette"), "suspicious_activity": ("SUSPICIOUS ACTIVITY", "eyes"),
         "property_damage": ("PROPERTY DAMAGE", "warning"), "tailgating": ("TAILGATING", "door")}


def ist(ts):
    return time.strftime("%H:%M:%S", time.gmtime(ts + 5.5 * 3600)) + " IST"


class Notifier(threading.Thread):
    def __init__(self, cfg=None, env=None, post=None, pager=None):
        """cfg: the notify: block; env: os.environ (tests pass a dict); post(url, **kw): httpx.post (tests pass a fake);
        pager: app.pager.Pager, the local-network channel (no internet)."""
        super().__init__(daemon=True, name="notify")
        self.cfg, env = dict(C if cfg is None else cfg), os.environ if env is None else env
        self.enabled = bool(self.cfg.get("enabled", False))
        self.ntfy = env.get("HACKHIVE_NTFY_URL") or None
        self.tg_token, self.tg_chat = env.get("HACKHIVE_TELEGRAM_TOKEN") or None, env.get("HACKHIVE_TELEGRAM_CHAT") or None
        self.q = queue.Queue(maxsize=int(self.cfg.get("queue", 50)))
        self.last_sent = {}                                  # (camera, category) -> time of the last message
        self.log = deque(maxlen=50)                          # (ts, event_id, channel, ok, ms, error)
        self.dropped = 0
        self._post = post
        self.pager = pager
        self._halt = False

    # ---- called from the pipeline thread: never blocks, never raises ----
    def channels(self):
        return [c for c, on in (("pager", self.pager), ("ntfy", self.ntfy), ("telegram", self.tg_token and self.tg_chat)) if on]

    def alert(self, ev, camera_name=None):
        try:
            if not self.enabled or not self.channels():
                return False
            cat, conf = ev.get("category"), float(ev.get("peak_confidence") or 0)
            if cat not in self.cfg.get("categories", ["fire_smoke", "fighting", "person_down", "crowd_incident"]):
                return False
            if conf < float(self.cfg.get("min_confidence", 0.6)) or ev.get("seeded"):
                return False
            key, now = (ev.get("camera_id"), cat), time.time()
            if now - self.last_sent.get(key, 0) < float(self.cfg.get("cooldown_s", 60)):
                return False
            self.last_sent[key] = now
            msg = {"event_id": ev.get("id"), "category": cat, "camera": camera_name or ev.get("camera_id"), "confidence": conf,
                   "ts": ev.get("_t_alert") or now, "summary": ev.get("summary") if self.cfg.get("include_summary") else None,
                   "queued": now}
            try:
                self.q.put_nowait(msg)
            except queue.Full:                               # keep the newest: drop the oldest
                try:
                    self.q.get_nowait()
                except queue.Empty:
                    pass
                self.dropped += 1
                self.q.put_nowait(msg)
            return True
        except Exception as e:                               # a notification problem must never touch the alert
            print(f"[notify] skipped: {e!r}", flush=True)
            return False

    def status(self):
        return {"enabled": self.enabled, "channels": self.channels(), "queued": self.q.qsize(), "dropped": self.dropped,
                "pager": {"urls": self.pager.urls(), "phones": self.pager.phones()} if self.pager else None,
                "cooldown_s": self.cfg.get("cooldown_s", 60), "min_confidence": self.cfg.get("min_confidence", 0.6),
                "recent": [{"ts": t, "event_id": e, "channel": c, "ok": ok, "ms": ms, "error": err} for t, e, c, ok, ms, err in list(self.log)[-10:]]}

    def stop(self):
        self._halt = True
        self.q.put_nowait(None) if not self.q.full() else None

    # ---- the worker thread ----
    def text(self, m):
        title, _ = LABEL.get(m["category"], (m["category"].upper(), "warning"))
        lines = [f"{title} at {m['camera']}", f"{ist(m['ts'])} · confidence {round(100 * m['confidence'])}% · event #{m['event_id']}"]
        if m.get("summary"):
            lines.append(m["summary"])
        lines.append("Automated alert from HoneyView. Check the camera before acting.")
        return title, "\n".join(lines)

    def send(self, m):
        post = self._post
        if post is None:
            import httpx
            post = httpx.post
        title, body = self.text(m)
        timeout = float(self.cfg.get("timeout_s", 3))
        for ch in self.channels():
            t0, ok, err = time.time(), False, None
            try:
                if ch == "pager":                            # local network, no internet: straight to open phone pages
                    n = self.pager.push({"title": title, "camera": m["camera"], "ts": m["ts"], "confidence": m["confidence"],
                                         "event_id": m["event_id"]})
                    ok, err = n > 0, None if n else "no phone connected"
                    self.log.append((time.time(), m["event_id"], ch, ok, round((time.time() - m["queued"]) * 1000), err))
                    continue
                if ch == "ntfy":
                    tag = LABEL.get(m["category"], ("", "warning"))[1]
                    r = post(self.ntfy, content=body.encode("utf-8"), timeout=timeout,
                             headers={"Title": title.encode("utf-8"), "Priority": "urgent" if m["category"] == "fire_smoke" else "high", "Tags": tag})
                else:
                    r = post(f"https://api.telegram.org/bot{self.tg_token}/sendMessage", timeout=timeout,
                             json={"chat_id": self.tg_chat, "text": f"{title}\n{body}", "disable_web_page_preview": True})
                ok = 200 <= r.status_code < 300
                err = None if ok else f"HTTP {r.status_code}"
            except Exception as e:                           # offline, DNS, timeout: logged, never raised
                err = type(e).__name__
            self.log.append((time.time(), m["event_id"], ch, ok, round((time.time() - m["queued"]) * 1000), err))
            if not ok:
                print(f"[notify] {ch} failed for event #{m['event_id']}: {err}", flush=True)

    def run(self):
        while not self._halt:
            m = self.q.get()
            if m is None:
                break
            self.send(m)


def selfcheck():
    """Fake HTTP endpoint, no internet: off by default, filters, cooldown, non-blocking with a 2 s slow server, payload."""
    class R:
        def __init__(self, code): self.status_code = code
    calls, slow = [], [0.0]

    def fake_post(url, **kw):
        time.sleep(slow[0]); calls.append((url, kw)); return R(200)
    cfg = {"enabled": False, "categories": ["fire_smoke", "fighting"], "min_confidence": 0.6, "cooldown_s": 60, "timeout_s": 3}
    env = {"HACKHIVE_NTFY_URL": "http://fake/topic", "HACKHIVE_TELEGRAM_TOKEN": "T", "HACKHIVE_TELEGRAM_CHAT": "@c"}
    n = Notifier(cfg, env, fake_post); n.start()
    ev = {"id": 41, "camera_id": "cam1", "category": "fire_smoke", "peak_confidence": 0.93, "_t_alert": time.time(), "summary": "smoke in a kitchen"}
    assert not n.alert(ev), "off by default"
    n.enabled = True
    assert n.alert(ev, "Lobby")
    assert not n.alert(ev, "Lobby"), "cooldown per camera + category"
    assert not n.alert(dict(ev, camera_id="cam2", category="normal")), "category filter"
    assert not n.alert(dict(ev, camera_id="cam3", peak_confidence=0.4)), "confidence filter"
    assert not n.alert(dict(ev, camera_id="cam4", seeded=1)), "seeded history never notifies"
    t0 = time.time()
    while len(calls) < 2 and time.time() - t0 < 3:
        time.sleep(0.02)
    (u1, k1), (u2, k2) = calls
    assert u1 == "http://fake/topic" and b"FIRE / SMOKE at Lobby" in k1["content"] and b"smoke in a kitchen" not in k1["content"], k1
    assert k1["headers"]["Priority"] == "urgent" and u2.endswith("/botT/sendMessage") and k2["json"]["chat_id"] == "@c"
    slow[0] = 2.0                                           # a dead-slow network: the caller still returns at once
    t0 = time.time()
    for i in range(80):
        n.alert(dict(ev, camera_id=f"x{i}"), "X")
    caller_ms = (time.time() - t0) * 1000
    assert caller_ms < 50, caller_ms
    assert n.dropped > 0 and n.q.qsize() <= 50, (n.dropped, n.q.qsize())
    st = n.status()
    assert st["enabled"] and st["channels"] == ["ntfy", "telegram"] and st["recent"][0]["ok"]
    n.stop()
    print(f"notify self-check ok: off by default, filters, cooldown, payload has no summary, 80 alerts queued in {caller_ms:.1f} ms "
          f"against a 2 s server, {n.dropped} oldest dropped")


def main():
    import sys
    if "--test" not in sys.argv:
        return selfcheck()
    n = Notifier(dict(C, enabled=True, cooldown_s=0))
    if not n.channels():
        raise SystemExit("no channel: set HACKHIVE_NTFY_URL and/or HACKHIVE_TELEGRAM_TOKEN + HACKHIVE_TELEGRAM_CHAT")
    n.send({"event_id": 0, "category": "fire_smoke", "camera": "TEST camera", "confidence": 1.0, "ts": time.time(), "queued": time.time()})
    for t, e, c, ok, ms, err in n.log:
        print(f"{c}: {'sent' if ok else 'FAILED ' + str(err)} in {ms} ms")


if __name__ == "__main__":
    main()
