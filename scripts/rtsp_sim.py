"""Minimal RTSP server: loops one clip as H.264/RTP for the dashboard's Live mode.

ffmpeg 8 has no RTSP listen mode and no RTSP server (mediamtx, VLC) is installed, so this script is
the server: ffmpeg encodes the clip in a loop and sends RTP to a local UDP port, and this script speaks
just enough RTSP (OPTIONS, DESCRIBE, SETUP, PLAY, GET_PARAMETER, TEARDOWN) to fan those packets out to
every client, over UDP or TCP-interleaved. Clients may join at any time (<= 1 s wait for a keyframe).

Usage: uv run python scripts/rtsp_sim.py data/dev/fighting/v011.avi [--port 8554]
       then add rtsp://127.0.0.1:8554/live in Live mode. Ctrl-C or SIGTERM stops ffmpeg too.
"""
import argparse, os, re, select, signal, socket, subprocess, sys, tempfile, threading, time
from urllib.parse import urlsplit

clients, lock, seq = [], threading.Lock(), [0]      # clients: send(pkt) callables of playing clients; seq: last RTP seq


def handle(c, ip, sdp, tx):
    """One RTSP client (one TCP connection) until TEARDOWN, EOF, an error or 90 s of silence."""
    f, sid, clock, send = c.makefile("rb"), os.urandom(4).hex(), threading.Lock(), None

    def reply(cseq, extra="", body=b"", status="200 OK"):
        hdr = f"RTSP/1.0 {status}\r\nCSeq: {cseq}\r\nSession: {sid};timeout=60\r\n{extra}"
        hdr += f"Content-Length: {len(body)}\r\n" if body else ""
        with clock:
            c.sendall(hdr.encode() + b"\r\n" + body)

    def send_tcp(pkt):                                  # RTP interleaved on the control socket, channel 0
        with clock:
            c.sendall(b"$\x00" + len(pkt).to_bytes(2, "big") + pkt)

    try:
        while first := f.read(1):
            if first == b"$":                           # interleaved RTCP from the client: skip it
                f.read(int.from_bytes(f.read(3)[1:], "big"))
                continue
            line = first + f.readline()
            if not line.strip():
                continue
            method, url = line.decode().split()[:2]
            h = {}
            while hl := f.readline().strip():
                k, _, v = hl.decode().partition(":")
                h[k.strip().lower()] = v.strip()
            f.read(int(h.get("content-length", 0)))     # discard any body
            cseq = h.get("cseq", "0")
            if method == "OPTIONS":
                reply(cseq, "Public: OPTIONS, DESCRIBE, SETUP, PLAY, TEARDOWN, GET_PARAMETER\r\n")
            elif method == "DESCRIBE":
                if urlsplit(url).path.rstrip("/") != "/live":
                    reply(cseq, status="404 Not Found")
                else:
                    reply(cseq, f"Content-Type: application/sdp\r\nContent-Base: {url.rstrip('/')}/\r\n", sdp)
            elif method == "SETUP":
                t = h["transport"].split(",")[0]
                if "TCP" in t.upper():
                    send = send_tcp
                    reply(cseq, f"Transport: {t}\r\n")
                else:
                    dest = (ip, int(re.search(r"client_port=(\d+)", t).group(1)))
                    send = lambda pkt: tx.sendto(pkt, dest)
                    p = tx.getsockname()[1]
                    reply(cseq, f"Transport: {t};server_port={p}-{p + 1}\r\n")
            elif method == "PLAY":
                reply(cseq, f"RTP-Info: url={url.rstrip('/')}/streamid=0;seq={(seq[0] + 1) & 0xFFFF}\r\n")
                with lock:
                    if send and send not in clients:
                        clients.append(send)
            elif method == "TEARDOWN":
                reply(cseq)
                break
            else:                                       # GET_PARAMETER keep-alive and anything else
                reply(cseq)
    except (OSError, ValueError, AttributeError, KeyError):
        pass
    finally:
        with lock:
            if send in clients:
                clients.remove(send)
        c.close()


def serve(srv, sdp, tx):
    while True:
        c, (ip, _) = srv.accept()
        c.settimeout(90)                                # ffmpeg keep-alives every ~30 s; 90 s of silence = dead client
        threading.Thread(target=handle, args=(c, ip, sdp, tx), daemon=True).start()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("clip"), ap.add_argument("--port", type=int, default=8554)
    a = ap.parse_args()
    rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); rx.bind(("127.0.0.1", 0))   # ffmpeg -> here
    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); tx.bind(("0.0.0.0", 0))     # here -> UDP clients
    srv = socket.socket(); srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        srv.bind(("0.0.0.0", a.port))
    except OSError as e:
        sys.exit(f"cannot listen on port {a.port}: {e}")
    srv.listen()
    for sig in (signal.SIGINT, signal.SIGTERM):            # SystemExit -> the finally below stops ffmpeg
        signal.signal(sig, lambda *_: sys.exit(0))
    with tempfile.TemporaryDirectory() as tmp:
        sdp_file = os.path.join(tmp, "live.sdp")
        proc = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-re", "-stream_loop", "-1", "-i", a.clip,
                                 "-an", "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency", "-threads", "2",
                                 "-g", "30", "-f", "rtp", "-sdp_file", sdp_file, f"rtp://127.0.0.1:{rx.getsockname()[1]}"],
                                stdin=subprocess.DEVNULL)
        try:
            sdp = ""
            while not ("m=video" in sdp and sdp.endswith("\n")):   # wait for ffmpeg to write the SDP
                if proc.poll() is not None:
                    sys.exit(f"ffmpeg exited with code {proc.returncode} before writing the SDP")
                time.sleep(0.1)
                sdp = open(sdp_file).read() if os.path.exists(sdp_file) else ""
            sdp = (re.sub(r"(m=video) \d+", r"\1 0", sdp).strip() + "\r\na=control:streamid=0\r\n").encode()
            threading.Thread(target=serve, args=(srv, sdp, tx), daemon=True).start()
            print(f"rtsp://127.0.0.1:{a.port}/live  <- add this in Live mode (Ctrl-C to stop)", flush=True)
            while True:                                     # fan ffmpeg's RTP packets out to every playing client
                if proc.poll() is not None:
                    sys.exit(f"ffmpeg exited with code {proc.returncode}")
                if not select.select([rx], [], [], 1)[0]:
                    continue
                pkt = rx.recv(65535)
                seq[0] = int.from_bytes(pkt[2:4], "big")
                with lock:
                    sinks = list(clients)
                for send in sinks:
                    try:
                        send(pkt)
                    except OSError:                         # ponytail: a stalled TCP client blocks the others for up to 90 s
                        with lock:
                            if send in clients:
                                clients.remove(send)
        finally:
            proc.terminate()
            try:
                proc.wait(5)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    main()
