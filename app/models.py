"""Model arbiter: ONE worker in front of the one Ollama slot, strict priority (SPEC §5a step 5, FR-8a, E-1, E-2).

Priorities: 1 gate-triggered incident (round-robin across cameras) → 2 chat → 3 baseline → 4 re-look.
Preemption: a P1 arriving while a P2/P3/P4 runs sets that request's `cancel` (the VLM client closes the stream and
Ollama stops; chat retries its call, FR-8a); a running P1 is never cancelled. Also measures GPU duty = share of wall time a call is running (§12).
Stale requests: a P4 re-look whose frames are older than `stale_s` when it reaches the head is dropped and counted
(its frames no longer show "now"); P1s are never dropped (frozen frames, SPEC §5a step 5), P3 baselines build their
mosaic at dispatch so they are never stale, P2 chat is never dropped. stats() reports queue wait and run time by
priority, cancellations, stale drops, per-camera starvation and GPU duty over time (FR-8a instrumentation).
"""
import threading
import time
from collections import deque


class Arbiter(threading.Thread):
    def __init__(self, run, stale_s=6.0):
        """run(req) does the model call; req is a dict with at least prio, cam, created; 'cancel' is added here."""
        super().__init__(daemon=True, name="arbiter")
        self.run_fn, self.q, self.running = run, [], None
        self.cv = threading.Condition()
        self.busy = deque()            # (start, end) of finished calls, for GPU duty
        self._rr, self._stop = None, False
        self.stale_s = stale_s
        self.log = deque(maxlen=5000)  # finished requests: (prio, cam, created, start, end, cancelled)
        self.dropped = deque(maxlen=1000)   # (prio, cam, created, dropped_at, reason)

    def submit(self, req):
        req.setdefault("created", time.time())
        req["cancel"] = threading.Event()
        with self.cv:
            self.q.append(req)
            if req["prio"] == 1 and self.running and self.running["prio"] >= 2:
                self.running["cancel"].set()
            self.cv.notify()
        return req

    def waiting(self, prio=None, cam=None):
        with self.cv:
            return [r for r in self.q if (prio is None or r["prio"] == prio) and (cam is None or r["cam"] == cam)]

    def drop(self, req):
        with self.cv:
            if req in self.q:
                self.q.remove(req)

    def _drop_stale(self, now):
        for r in [r for r in self.q if r["prio"] == 4 and now - r["created"] > self.stale_s]:
            self.q.remove(r)
            self.dropped.append((r["prio"], r["cam"], r["created"], now, "stale"))
            if r.get("on_drop"):
                r["on_drop"](r)

    def _pick(self):
        self._drop_stale(time.time())
        if not self.q:
            return None
        top = min(r["prio"] for r in self.q)
        cands = [r for r in self.q if r["prio"] == top]
        if top == 1:  # round-robin across cameras: next camera after the last one served, its oldest request
            cams = sorted({r["cam"] for r in cands})
            nxt = next((c for c in cams if self._rr is None or c > self._rr), cams[0])
            cands = [r for r in cands if r["cam"] == nxt]
            self._rr = nxt
        req = min(cands, key=lambda r: r["created"])
        self.q.remove(req)
        return req

    def run(self):
        while True:
            with self.cv:
                while not self.q and not self._stop:
                    self.cv.wait()
                if self._stop:
                    return
                self.running = req = self._pick()
                if req is None:
                    continue
                t0 = req["t_start"] = time.time()
            try:
                self.run_fn(req)
            except Exception as e:  # a failed call never kills the arbiter (E-5)
                print(f"[arbiter] {req.get('cam')} P{req['prio']} failed: {e!r}", flush=True)
            with self.cv:
                self.running = None
                t1 = time.time()
                self.busy.append((t0, t1))
                self.log.append((req["prio"], req.get("cam"), req["created"], t0, t1, req["cancel"].is_set()))

    def duty(self, window=60.0, now=None):
        """Share of the last `window` seconds a model call was running (§12)."""
        now = now or time.time()
        with self.cv:
            busy = list(self.busy) + ([(self.running["t_start"], now)] if self.running else [])
        while self.busy and self.busy[0][1] < now - 600:
            self.busy.popleft()
        return sum(max(0.0, min(e, now) - max(s, now - window)) for s, e in busy) / window

    def stats(self, now=None, window=None):
        """Instrumentation: per priority n / queue wait / run time (ms p50, p95, max) / cancelled; stale drops; per camera
        served, worst queue wait and the age of its oldest request still waiting (starvation); GPU duty per 10 s."""
        now = now or time.time()
        with self.cv:
            log = [x for x in self.log if window is None or x[4] >= now - window]
            waiting = [(r["prio"], r["cam"], now - r["created"]) for r in self.q]
            dropped = list(self.dropped)

        def q(xs):
            xs = sorted(xs)
            return {"p50": round(xs[len(xs) // 2]), "p95": round(xs[min(len(xs) - 1, int(0.95 * len(xs)))]),
                    "max": round(xs[-1])} if xs else None
        by_prio = {}
        for p in sorted({x[0] for x in log}):
            xs = [x for x in log if x[0] == p]
            by_prio[f"P{p}"] = {"n": len(xs), "queue_ms": q([(x[3] - x[2]) * 1000 for x in xs]),
                                "run_ms": q([(x[4] - x[3]) * 1000 for x in xs]), "cancelled": sum(x[5] for x in xs)}
        by_cam = {}
        for c in sorted({x[1] for x in log if x[1]} | {w[1] for w in waiting if w[1]}):
            xs = [x for x in log if x[1] == c]
            by_cam[c] = {"served": len(xs), "queue_ms": q([(x[3] - x[2]) * 1000 for x in xs]),
                         "oldest_waiting_ms": round(max((a for _, cam, a in waiting if cam == c), default=0) * 1000)}
        span = window or 60.0
        timeline = [round(self.duty(window=10.0, now=now - k * 10.0), 3) for k in range(int(span // 10) - 1, -1, -1)]
        return {"by_priority": by_prio, "by_camera": by_cam, "waiting": len(waiting),
                "dropped_stale": len(dropped), "duty_last_60s": round(self.duty(60.0, now), 3), "duty_per_10s": timeline}

    def stop(self):
        with self.cv:
            self._stop = True
            self.cv.notify()


if __name__ == "__main__":
    log = []
    def fake(req):  # a model call: 0.3 s, stops early if cancelled
        for _ in range(30):
            if req["cancel"].is_set():
                log.append((req["name"], "cancelled")); return
            time.sleep(0.01)
        log.append((req["name"], "done"))
    a = Arbiter(fake); a.start()
    a.submit({"prio": 3, "cam": "cam1", "name": "base1"})
    time.sleep(0.05)
    # While base1 runs: two P1s on cam1, one on cam2, and a P3 -> base1 is cancelled, P1s round-robin, P3 last.
    a.submit({"prio": 1, "cam": "cam1", "name": "p1a"}); a.submit({"prio": 1, "cam": "cam1", "name": "p1b"})
    a.submit({"prio": 1, "cam": "cam2", "name": "p1c"}); a.submit({"prio": 3, "cam": "cam2", "name": "base2"})
    time.sleep(1.6)
    print(log)
    assert log == [("base1", "cancelled"), ("p1a", "done"), ("p1c", "done"), ("p1b", "done"), ("base2", "done")], log
    d = a.duty(window=2.0)
    assert 0.55 < d < 0.85, d   # ~1.25 s busy in the last 2 s
    a.submit({"prio": 2, "cam": "chat", "name": "chat"}); time.sleep(0.05)
    a.submit({"prio": 1, "cam": "cam1", "name": "p1d"}); time.sleep(0.7)
    assert log[-2:] == [("chat", "cancelled"), ("p1d", "done")], log   # a P1 cancels a running chat call (FR-8a)
    a.stop()
    print("models (arbiter) self-check ok, duty %.2f" % d)
