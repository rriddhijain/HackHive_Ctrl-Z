"""Model arbiter: ONE worker in front of the one Ollama slot, strict priority (SPEC §5a step 5, FR-8a, E-1, E-2).

Priorities: 1 gate-triggered incident (round-robin across cameras) → 2 chat → 3 baseline → 4 re-look.
Preemption: a P1 arriving while a P3/P4 runs sets that request's `cancel` (the VLM client closes the stream and
Ollama stops); a running P1 is never cancelled. Also measures GPU duty = share of wall time a call is running (§12).
"""
import threading
import time
from collections import deque


class Arbiter(threading.Thread):
    def __init__(self, run):
        """run(req) does the model call; req is a dict with at least prio, cam, created; 'cancel' is added here."""
        super().__init__(daemon=True, name="arbiter")
        self.run_fn, self.q, self.running = run, [], None
        self.cv = threading.Condition()
        self.busy = deque()            # (start, end) of finished calls, for GPU duty
        self._rr, self._stop = None, False

    def submit(self, req):
        req.setdefault("created", time.time())
        req["cancel"] = threading.Event()
        with self.cv:
            self.q.append(req)
            if req["prio"] == 1 and self.running and self.running["prio"] >= 3:
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

    def _pick(self):
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
                t0 = req["t_start"] = time.time()
            try:
                self.run_fn(req)
            except Exception as e:  # a failed call never kills the arbiter (E-5)
                print(f"[arbiter] {req.get('cam')} P{req['prio']} failed: {e!r}", flush=True)
            with self.cv:
                self.running = None
                self.busy.append((t0, time.time()))

    def duty(self, window=60.0, now=None):
        """Share of the last `window` seconds a model call was running (§12)."""
        now = now or time.time()
        with self.cv:
            busy = list(self.busy) + ([(self.running["t_start"], now)] if self.running else [])
        while self.busy and self.busy[0][1] < now - 600:
            self.busy.popleft()
        return sum(max(0.0, min(e, now) - max(s, now - window)) for s, e in busy) / window

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
    a.stop()
    print("models (arbiter) self-check ok, duty %.2f" % d)
