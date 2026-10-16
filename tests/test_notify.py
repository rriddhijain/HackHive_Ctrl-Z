"""Opt-in phone notifications (app/notify.py, D89): off by default, filters, cooldown, never blocks the alert path."""
import time
import unittest

from app import notify


class Notify(unittest.TestCase):
    def test_selfcheck(self):
        notify.selfcheck()                       # fake endpoint: filters, cooldown, payload, 2 s server never blocks

    def test_no_channel_never_sends(self):
        n = notify.Notifier({"enabled": True}, env={})
        self.assertEqual(n.channels(), [])
        self.assertFalse(n.alert({"id": 1, "camera_id": "c", "category": "fire_smoke", "peak_confidence": 1.0}))

    def test_offline_failure_is_logged_not_raised(self):
        def down(url, **kw):
            raise OSError("network unreachable")
        n = notify.Notifier({"enabled": True}, env={"HACKHIVE_NTFY_URL": "http://x"}, post=down)
        n.send({"event_id": 7, "category": "fighting", "camera": "c", "confidence": 0.9, "ts": time.time(), "queued": time.time()})
        self.assertEqual((n.log[-1][2], n.log[-1][3], n.log[-1][5]), ("ntfy", False, "OSError"))


if __name__ == "__main__":
    unittest.main()
