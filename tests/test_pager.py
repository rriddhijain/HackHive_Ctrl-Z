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


if __name__ == "__main__":
    unittest.main()
