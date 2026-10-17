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

    def ev(self, **kw):
        return dict({"id": 1, "camera_id": "c", "category": "fire_smoke", "peak_confidence": 1.0}, **kw)

    def test_cooldown_released_when_nothing_delivered(self):
        # A phone that joins after the first alert must get the next one from that camera, not wait out the cooldown.
        class R:
            status_code = 500
        n = notify.Notifier({"enabled": True, "cooldown_s": 60}, env={"HACKHIVE_NTFY_URL": "http://x"}, post=lambda u, **k: R())
        self.assertTrue(n.alert(self.ev()))
        self.assertFalse(n.send(n.q.get_nowait()))
        self.assertTrue(n.alert(self.ev(id=2)), "nothing went out, so the cooldown must not be spent")

    def test_cooldown_kept_after_delivery(self):
        class R:
            status_code = 200
        n = notify.Notifier({"enabled": True, "cooldown_s": 60}, env={"HACKHIVE_NTFY_URL": "http://x"}, post=lambda u, **k: R())
        self.assertTrue(n.alert(self.ev()))
        self.assertTrue(n.send(n.q.get_nowait()))
        self.assertFalse(n.alert(self.ev(id=2)))

    def test_test_message_never_raises_when_full(self):
        n = notify.Notifier({"enabled": False, "queue": 2}, env={"HACKHIVE_NTFY_URL": "http://x"})
        for _ in range(5):
            n.test()                             # was queue.Full -> HTTP 500 from POST /api/notify/test
        self.assertEqual((n.q.qsize(), n.dropped), (2, 3))

    def test_switched_off_while_queued_is_not_sent(self):
        sent = []

        class R:
            status_code = 200
        n = notify.Notifier({"enabled": True}, env={"HACKHIVE_NTFY_URL": "http://x"}, post=lambda u, **k: sent.append(u) or R())
        self.assertTrue(n.alert(self.ev()))
        n.test()
        n.enabled = False
        n.start()
        t = time.time()
        while n.q.qsize() and time.time() - t < 2:
            time.sleep(0.01)
        time.sleep(0.05)
        n.stop()
        self.assertEqual(len(sent), 1, "only the test message goes out after switching off")
        self.assertEqual(n.log[-1][1], 0)


if __name__ == "__main__":
    unittest.main()
