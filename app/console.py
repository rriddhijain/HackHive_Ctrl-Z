"""ESP32 guard console bridge (D89): USB serial <-> the alert path, stdlib only (termios, no pyserial).

The board (firmware/esp32/console) is a hardware stopwatch and alarm light. Press its button when an incident starts
(MARK); the first alert after that comes back as LAT <id> <ms>: onset -> alert as the operator saw it, measured on the
board's own clock (D50: the number a judge times). Every alert is sent as ALERT <id> <severity> <category> and blinks
the LED until acknowledged; a press during an alarm sends ACK <id>, which acknowledges it exactly like the dashboard
button. PING every second is the link watchdog (the board double-blinks when the server or the cable is gone) and
carries the newest alert still waiting for an acknowledgement, so the LED follows the server even after a lost
message, a second alert or a restart; the board's PONG says what it shows (state["board_alarm"]).

The port is found by name (macOS USB-UART bridges) and reopened after an unplug; no board = the console stays idle and
nothing else changes. state is read by the server's metrics() for the dashboard's Console chip.

  uv run python -m app.console           self-check against a simulated board (a pty), no hardware
  uv run python -m app.console --board   live check on the real board: press BOOT, a test alert follows, prints LAT
"""
import glob
import os
import select
import termios
import threading
import time

PATTERNS = ("/dev/cu.usbserial-*", "/dev/cu.SLAB_USBtoUART*", "/dev/cu.wchusbserial*")
ALIVE_S = 3.0


def find_port():
    return next(iter(sorted(p for pat in PATTERNS for p in glob.glob(pat))), None)


def open_port(path):
    """Raw 8N1 at 115200, non-blocking. HUPCL off, so closing the port doesn't reset the board."""
    fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    a = termios.tcgetattr(fd)
    a[0] = a[1] = a[3] = 0                                          # iflag, oflag, lflag: raw
    a[2] = termios.CS8 | termios.CREAD | termios.CLOCAL             # cflag: 8 bits, no modem control, no HUPCL
    a[4] = a[5] = termios.B115200
    termios.tcsetattr(fd, termios.TCSANOW, a)
    return fd


class Console:
    def __init__(self, on_ack, port=None):
        self.on_ack, self.port = on_ack, port
        self.fd, self.lock, self.cats = None, threading.Lock(), {}
        self.pending = {}                                       # alerted, not yet acknowledged/dismissed: id -> severity
        self.seen, self.mark_ts = 0.0, None
        self.state = {"connected": False, "port": None, "timing": False, "last": None, "board_alarm": None}

    def start(self):
        threading.Thread(target=self.run, daemon=True, name="console").start()
        return self

    def send(self, msg):
        with self.lock:
            if self.fd is not None:
                try:
                    os.write(self.fd, (msg + "\n").encode())
                except OSError:
                    pass                                        # the reader notices the unplug and reopens

    def alert(self, ev):
        self.cats[ev["id"]] = ev["category"]
        self.pending[ev["id"]] = ev["severity"]
        self.send(f"ALERT {ev['id']} {ev['severity']} {ev['category']}")

    def clear(self, eid):
        self.pending.pop(eid, None)
        self.send(f"CLEAR {eid}")

    def ping(self):
        newest = list(self.pending.items())[-1:]
        self.send(f"PING {newest[0][0]} {newest[0][1]}" if newest else "PING -")

    def handle(self, line):
        self.seen = time.time()
        word, *args = line.split()
        if word == "MARK":
            self.mark_ts = self.seen
            self.state["timing"] = True
        elif word == "LAT" and len(args) == 2:
            eid, ms = int(args[0]), int(args[1])
            self.state.update(timing=False, last={"event_id": eid, "category": self.cats.get(eid), "ms": ms, "ts": self.seen})
            print(f"[console] onset -> alert {ms} ms (event {eid}, {self.cats.get(eid)})", flush=True)
        elif word == "PONG":
            self.state["board_alarm"] = int(args[0]) if args and args[0] != "-" else None
        elif word == "ACK" and args:
            self.pending.pop(int(args[0]), None)               # the board went dark already; never re-arm it
            try:
                self.on_ack(int(args[0]))
            except Exception as e:                              # an unknown id must never kill the reader
                print(f"[console] ack {args[0]}: {e!r}", flush=True)

    def run(self):
        while True:
            path = self.port or find_port()
            if not path:
                time.sleep(2)
                continue
            try:
                fd = open_port(path)
            except OSError:
                time.sleep(2)
                continue
            with self.lock:
                self.fd = fd
            self.state["port"] = path
            buf, last_ping = b"", 0.0
            try:
                while True:
                    now = time.time()
                    if now - last_ping >= 1:
                        self.ping(); last_ping = now
                    if select.select([fd], [], [], 0.05)[0]:
                        chunk = os.read(fd, 256)
                        if not chunk:
                            raise OSError("port closed")
                        buf += chunk
                        while b"\n" in buf:
                            raw, buf = buf.split(b"\n", 1)
                            # boot-ROM noise (another baud rate) can sit in front of the first line: keep the tail
                            if line := raw.decode(errors="replace").rsplit("\x00", 1)[-1].strip():
                                self.handle(line)
                    if self.state["timing"] and now - (self.mark_ts or now) > 30:
                        self.state["timing"] = False            # the board drops a mark after 30 s too
                    self.state["connected"] = now - self.seen < ALIVE_S
            except OSError:
                pass
            with self.lock:
                self.fd = None
            os.close(fd)
            self.state.update(connected=False, timing=False)
            time.sleep(1)


def _readline(fd, timeout=2.0):
    buf, end = b"", time.time() + timeout
    while time.time() < end and b"\n" not in buf:
        if select.select([fd], [], [], 0.05)[0]:
            buf += os.read(fd, 1)
    return buf.decode().strip()


def selfcheck():
    """A pty plays the board: ping, mark, alert -> LAT, ack, a bad ack, then an unplug."""
    import pty
    board, host = pty.openpty()
    acks = []

    def on_ack(eid):
        if eid == 99:
            raise KeyError(eid)                                 # like ack() on an unknown event id
        acks.append(eid)
    c = Console(on_ack, port=os.ttyname(host)).start()
    while (ln := _readline(board)) != "PING -":
        assert ln, "no PING from the bridge"
    os.write(board, b"HELLO hackhive-console 1\nMARK\n")
    time.sleep(0.2)
    assert c.state["connected"] and c.state["timing"], c.state
    c.alert({"id": 7, "severity": "critical", "category": "fighting"})
    while (ln := _readline(board)).startswith("PING"):
        pass
    assert ln == "ALERT 7 critical fighting", ln
    c.alert({"id": 8, "severity": "high", "category": "person_down"})
    while (ln := _readline(board)) != "PING 8 high":           # the newest unacknowledged alert rides on PING
        assert ln, "no PING carrying alert 8"
    os.write(board, b"PONG 8\nLAT 7 1234\nACK 7\nACK 99\n")
    time.sleep(0.3)
    assert c.state["board_alarm"] == 8 and list(c.pending) == [8], (c.state, c.pending)
    assert c.state["last"]["ms"] == 1234 and c.state["last"]["category"] == "fighting" and not c.state["timing"], c.state
    assert acks == [7], acks                                    # ACK 99 raised in on_ack: logged, reader alive
    c.clear(8)
    while (ln := _readline(board)).startswith("PING"):
        pass
    assert ln == "CLEAR 8", ln
    while (ln := _readline(board)) != "PING -":                # nothing left to acknowledge: the board goes dark
        assert ln, "no PING - after the last clear"
    print("console self-check ok: PING watchdog + alarm state, MARK -> LAT 1234 ms, ACK, bad ACK survived, CLEAR")


def board_check():
    """Real board: waits for a BOOT press, sends a test alert 1.5 s later, prints the board's LAT, waits for the ack."""
    acked = threading.Event()
    c = Console(on_ack=lambda eid: acked.set()).start()
    t = time.time() + 10
    while not c.state["connected"] and time.time() < t:
        time.sleep(0.2)
    assert c.state["connected"], f"no board answered on {find_port()}"
    print(f"board on {c.state['port']}. Press BOOT (stopwatch start)...", flush=True)
    while not c.state["timing"]:
        time.sleep(0.05)
    time.sleep(1.5)
    c.alert({"id": 1, "severity": "critical", "category": "fighting"})
    print("test alert sent: the LED blinks fast. Press BOOT again to acknowledge.", flush=True)
    assert acked.wait(60), "no ACK from the board within 60 s"
    print(f"board check ok: stopwatch {c.state['last']['ms']} ms (expected ~1,500), ACK received", flush=True)


if __name__ == "__main__":
    import sys
    board_check() if "--board" in sys.argv else selfcheck()
