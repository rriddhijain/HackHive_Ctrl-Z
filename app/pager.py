"""Local phone pager (D89): critical alerts pushed from this laptop straight to phones on the same Wi-Fi / hotspot.
No internet, no third-party service, no app: a phone opens the pager link once, taps "Enable alarm", and every
critical alert then turns its screen red, plays a siren and (Android) vibrates.

  uv run python -m app.pager          self-check: a fake phone subscribes over HTTP and receives one alert

Separate from the dashboard on purpose: the dashboard stays on 127.0.0.1 (it has controls and no auth); the pager
listens on the LAN (config pager.port, default 8100) and serves only two read-only things, both behind a random token:
  GET /?k=TOKEN          the phone page (inline HTML/JS, works offline)
  GET /events?k=TOKEN    Server-Sent Events: one "alert" message per notification, a comment ping every 15 s
Limits, said plainly: the page must stay open on the phone (browsers block background notifications from a plain
http:// LAN address); iPhones get the siren and red screen but no vibration.
"""
import json
import os
import queue
import secrets
import socket
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from app.config import CFG

C = CFG.get("pager") or {}

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><title>HoneyView Pager</title>
<style>
:root{--bg:#0A1628;--fg:#F3F5F8;--mut:#9AA6B8;--red:#C8102E;--ok:#2FB37F}
*{box-sizing:border-box}html,body{margin:0;height:100%;background:var(--bg);color:var(--fg);font:16px/1.4 -apple-system,system-ui,Segoe UI,Roboto,sans-serif}
main{min-height:100%;display:flex;flex-direction:column;gap:16px;padding:24px 20px}
h1{font-size:22px;margin:0}.mut{color:var(--mut);font-size:14px}
.pill{display:inline-flex;align-items:center;gap:8px;padding:6px 12px;border-radius:999px;background:#17294A;font-size:14px}
.dot{width:10px;height:10px;border-radius:50%;background:var(--mut)}.on .dot{background:var(--ok)}
button{font:inherit;font-weight:600;border:0;border-radius:14px;padding:16px;width:100%;background:var(--fg);color:var(--bg)}
#alarm{position:fixed;inset:0;display:none;flex-direction:column;justify-content:center;gap:14px;padding:28px;background:var(--red);animation:pulse 1s infinite}
#alarm.show{display:flex}#alarm h2{font-size:40px;line-height:1.05;margin:0}#alarm p{margin:0;font-size:20px}
#alarm button{background:#fff;color:var(--red);margin-top:18px}
@keyframes pulse{50%{background:#8E0B20}}
#log{list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:8px}
#log li{background:#17294A;border-radius:12px;padding:12px 14px;font-size:14px}
</style></head><body><main>
<h1>HoneyView Pager</h1>
<span id="st" class="pill"><span class="dot"></span><span id="stt">Connecting…</span></span>
<p class="mut">Keep this page open. Alerts come straight from the HoneyView laptop over this local network: no internet, no app.</p>
<button id="arm">Enable alarm sound</button>
<ul id="log"></ul>
</main>
<div id="alarm" role="alert"><h2 id="aT"></h2><p id="aW"></p><p id="aM"></p><button id="ack">Acknowledge</button></div>
<script>
const K=new URLSearchParams(location.search).get("k")||"";let ctx=null,siren=null,armed=false;
const $=id=>document.getElementById(id);
$("arm").onclick=()=>{ctx=ctx||new (window.AudioContext||window.webkitAudioContext)();ctx.resume();armed=true;
  $("arm").textContent="Alarm sound on";$("arm").disabled=true;beep(0.15);if(navigator.vibrate)navigator.vibrate(80)};
function beep(d){if(!ctx)return;const o=ctx.createOscillator(),g=ctx.createGain();o.type="square";o.frequency.value=880;g.gain.value=.2;
  o.connect(g).connect(ctx.destination);o.start();o.stop(ctx.currentTime+d)}
function startSiren(){if(!armed||siren)return;let hi=false;siren=setInterval(()=>{hi=!hi;if(!ctx)return;const o=ctx.createOscillator(),g=ctx.createGain();
  o.type="sawtooth";o.frequency.value=hi?960:640;g.gain.value=.25;o.connect(g).connect(ctx.destination);o.start();o.stop(ctx.currentTime+.42)},450)}
function stopSiren(){clearInterval(siren);siren=null;if(navigator.vibrate)navigator.vibrate(0)}
$("ack").onclick=()=>{$("alarm").classList.remove("show");stopSiren()};
function fmt(ts){return new Date(ts*1000).toLocaleTimeString("en-GB",{timeZone:"Asia/Kolkata",hour12:false})+" IST"}
function connect(){const es=new EventSource("/events?k="+encodeURIComponent(K));
  es.onopen=()=>{$("st").className="pill on";$("stt").textContent="Connected to HoneyView"};
  es.onerror=()=>{$("st").className="pill";$("stt").textContent="Reconnecting…"};
  es.addEventListener("alert",ev=>{const a=JSON.parse(ev.data);
    $("aT").textContent=a.title;$("aW").textContent="at "+a.camera;$("aM").textContent=fmt(a.ts)+" · confidence "+Math.round(a.confidence*100)+"%";
    $("alarm").classList.add("show");startSiren();if(navigator.vibrate)navigator.vibrate([600,200,600,200,600,200,600]);
    const li=document.createElement("li");li.textContent=fmt(a.ts)+"  "+a.title+" at "+a.camera;$("log").prepend(li)})}
connect();
</script></body></html>"""


def lan_ips():
    """IPv4 addresses phones on the same network can reach (offline-safe: no packets are sent)."""
    ips = set()
    try:
        out = subprocess.run(["ifconfig"], capture_output=True, text=True, timeout=2).stdout
        for line in out.splitlines():
            p = line.split()
            if len(p) > 1 and p[0] == "inet" and not p[1].startswith("127."):
                ips.add(p[1])
    except Exception:
        pass
    for probe in ("10.255.255.255", "192.168.255.255"):   # UDP "connect" picks the outgoing interface; nothing is sent
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sk:
                sk.connect((probe, 1)); ips.add(sk.getsockname()[0])
        except Exception:
            pass
    try:
        ips.add(socket.gethostbyname(socket.gethostname()))
    except Exception:
        pass
    return sorted(ip for ip in ips if not ip.startswith("127."))


class Pager:
    def __init__(self, port=None, token=None, host="0.0.0.0"):
        self.port = int(port if port is not None else C.get("port", 8100))   # 0 = any free port (tests)
        self.token = token or os.environ.get("HONEYVIEW_PAGER_TOKEN") or secrets.token_urlsafe(6)
        self.host, self.subs, self.lock = host, set(), threading.Lock()
        pager = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                u = urlparse(self.path)
                if parse_qs(u.query).get("k", [""])[0] != pager.token:
                    self.send_response(403); self.end_headers(); self.wfile.write(b"forbidden"); return
                if u.path == "/":
                    body = PAGE.encode()
                    self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body))); self.send_header("Cache-Control", "no-store"); self.end_headers()
                    self.wfile.write(body); return
                if u.path != "/events":
                    self.send_response(404); self.end_headers(); return
                self.send_response(200)
                for k, v in (("Content-Type", "text/event-stream"), ("Cache-Control", "no-store"), ("Connection", "keep-alive")):
                    self.send_header(k, v)
                self.end_headers()
                q = queue.Queue(maxsize=20)
                with pager.lock:
                    pager.subs.add(q)
                try:
                    self.wfile.write(b": connected\n\n"); self.wfile.flush()
                    while True:
                        try:
                            msg = q.get(timeout=15)
                            self.wfile.write(f"event: alert\ndata: {json.dumps(msg)}\n\n".encode())
                        except queue.Empty:
                            self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass
                finally:
                    with pager.lock:
                        pager.subs.discard(q)

        self.httpd = ThreadingHTTPServer((host, self.port), H)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]

    def start(self):
        threading.Thread(target=self.httpd.serve_forever, daemon=True, name="pager").start()
        return self

    def urls(self):
        return [f"http://{ip}:{self.port}/?k={self.token}" for ip in lan_ips()] or [f"http://<this-laptop-ip>:{self.port}/?k={self.token}"]

    def phones(self):
        with self.lock:
            return len(self.subs)

    def push(self, msg):
        """Called from the notifier's worker thread. Returns how many phones it was queued for."""
        n = 0
        with self.lock:
            subs = list(self.subs)
        for q in subs:
            try:
                q.put_nowait(msg); n += 1
            except queue.Full:
                pass
        return n

    def stop(self):
        self.httpd.shutdown()


def selfcheck():
    import http.client
    p = Pager(port=0, token="t0k", host="127.0.0.1")
    assert p.port != 0 and p.port != C.get("port", 8100), "port=0 must bind a free port, never the real pager's"
    p.start()
    c = http.client.HTTPConnection("127.0.0.1", p.port, timeout=5)
    c.request("GET", "/?k=wrong"); r = c.getresponse(); r.read()
    assert r.status == 403, r.status
    c.request("GET", "/?k=t0k"); r = c.getresponse(); body = r.read()
    assert r.status == 200 and b"HoneyView Pager" in body and b"http" not in body.split(b"<script>")[1].split(b"EventSource")[0], "page"
    assert b"cdn" not in body.lower() and b"https://" not in body, "the page loads nothing from the internet"
    s = http.client.HTTPConnection("127.0.0.1", p.port, timeout=5)
    s.request("GET", "/events?k=t0k"); r = s.getresponse()
    assert r.status == 200 and r.getheader("Content-Type") == "text/event-stream"
    assert r.fp.readline().startswith(b": connected")
    t0 = time.time()
    while p.phones() == 0 and time.time() - t0 < 2:
        time.sleep(0.02)
    assert p.phones() == 1
    t0 = time.time()
    n = p.push({"title": "FIRE / SMOKE", "camera": "Lobby", "ts": time.time(), "confidence": 0.93, "event_id": 41})
    lines = [l for l in (r.fp.readline() for _ in range(3)) if l.strip()]
    ms = (time.time() - t0) * 1000
    assert n == 1 and lines[0] == b"event: alert\n" and b'"camera": "Lobby"' in lines[1], lines
    p.stop()
    print(f"pager self-check ok: token enforced, page has no internet dependency, a subscribed phone got the alert in {ms:.1f} ms")


if __name__ == "__main__":
    selfcheck()
