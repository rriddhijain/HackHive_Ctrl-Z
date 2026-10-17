"""Local phone pager (app/pager.py, D89): token, offline page, delivery to a subscribed phone; notifier channel."""
import time
import unittest

from app import notify, pager


class Pager(unittest.TestCase):
    def test_selfcheck(self):
        pager.selfcheck()

    def test_pager_channel_reports_no_phone(self):
        p = pager.Pager(port=0, token="t", host="127.0.0.1")
        n = notify.Notifier({"enabled": True}, env={}, pager=p)
        self.assertEqual(n.channels(), ["pager"])
        n.send({"event_id": 3, "category": "fire_smoke", "camera": "Lobby", "confidence": 1.0, "ts": time.time(), "queued": time.time()})
        self.assertEqual((n.log[-1][2], n.log[-1][3], n.log[-1][5]), ("pager", False, "no phone connected"))
        p.httpd.server_close()

    def test_port_zero_is_ephemeral_even_with_the_real_pager_running(self):
        import socket
        busy = socket.socket(); busy.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            busy.bind(("127.0.0.1", pager.C.get("port", 8100))); busy.listen()
        except OSError:
            pass                                 # already taken by a real pager: even better
        try:
            p = pager.Pager(port=0, token="t", host="127.0.0.1")
            self.assertNotIn(p.port, (0, pager.C.get("port", 8100)))
            p.httpd.server_close()
        finally:
            busy.close()


if __name__ == "__main__":
    unittest.main()
