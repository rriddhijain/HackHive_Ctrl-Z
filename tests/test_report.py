"""Report tab accuracy block (bench.metrics.dev_report, used by GET /api/report) on old, partial and odd benchmark
files, and the arbiter instrumentation behind GET /api/arbiter. Stdlib unittest; no model, no OpenCV."""
import csv
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from bench import metrics
from bench.metrics import dev_report, num

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "bench" / "results"
COLS = ["clip", "label", "pred", "confidence", "onset_to_alert_ms", "onset_to_gate_ms", "trigger_to_alert_ms", "summary"]


class Report(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())

    def make(self, rows=None, summary=None, cols=COLS, tag="t"):
        """Write ab_dev_<tag>_summary.json (+ the CSV unless rows is None)."""
        p = self.d / f"ab_dev_{tag}_summary.json"
        p.write_text(json.dumps({"v": summary if summary is not None else {"macro_f1": 0.5}}), encoding="utf-8")
        if rows is not None:
            with open(self.d / f"ab_dev_{tag}.csv", "w", encoding="utf-8", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(rows)
        return p

    def test_historical_pass_still_0641(self):
        p = RES / "ab_dev_p6b_summary.json"
        r = dev_report(p, {}, 4.0)
        self.assertEqual(r["observed_label_macro_f1"], 0.641)
        self.assertEqual(r["macro_f1"], 0.641)                      # the stored key the dashboard always read
        self.assertIn("fixed", r)
        json.dumps(r)

    def test_no_csv(self):
        r = dev_report(self.make(None), {}, 4.0)
        self.assertEqual(r["clips"], [])
        self.assertIsNone(r["observed_label_macro_f1"])
        self.assertEqual(r["onset_to_alert_n"], 0)
        self.assertEqual(r["onset_to_alert_p50_p95"], (None, None))

    def test_empty_csv_and_empty_file(self):
        r = dev_report(self.make([]), {}, 4.0)
        self.assertEqual(r["clips"], [])
        (self.d / "ab_dev_e.csv").write_text("", encoding="utf-8")
        (self.d / "ab_dev_e_summary.json").write_text("{}", encoding="utf-8")
        r = dev_report(self.d / "ab_dev_e_summary.json", {}, 4.0)
        self.assertEqual((r["clips"], r["tag"]), ([], "e"))

    def test_unreadable_summary(self):
        (self.d / "ab_dev_b_summary.json").write_text("{not json", encoding="utf-8")
        r = dev_report(self.d / "ab_dev_b_summary.json", {}, 4.0)
        self.assertEqual(r["tag"], "b")
        self.assertIn("fixed", r)

    def test_old_summary_without_fixed(self):
        rows = [{"clip": "a.mp4", "label": "fighting", "pred": "fighting"}, {"clip": "b.mp4", "label": "normal", "pred": "normal"}]
        r = dev_report(self.make(rows, {"macro_f1": 1.0}, cols=["clip", "label", "pred"]), {}, 4.0)
        self.assertEqual(r["fixed"]["labels"], metrics.LABELS)       # recomputed, not missing
        self.assertEqual(r["fixed"]["supported_classes"], ["fighting", "normal"])
        self.assertIsNone(r["clips"][0]["onset_to_alert_ms"])        # missing column -> None, not a crash

    def test_unicode_summary(self):
        s = "Two people shove — one falls; “stop” 🚨 café"
        r = dev_report(self.make([{"clip": "a.mp4", "label": "fighting", "pred": "fighting", "summary": s}]), {}, 4.0)
        self.assertEqual(r["clips"][0]["summary"], s)
        json.dumps(r, ensure_ascii=False)

    def test_zero_and_blank_timings(self):
        rows = [{"clip": "z.mp4", "label": "fighting", "pred": "fighting", "onset_to_alert_ms": "0", "onset_to_gate_ms": "0"},
                {"clip": "n.mp4", "label": "fighting", "pred": "fighting", "onset_to_alert_ms": "", "onset_to_gate_ms": "None"},
                {"clip": "x.mp4", "label": "fighting", "pred": "fighting", "onset_to_alert_ms": "nan"},
                {"clip": "m.mp4", "label": "fighting", "pred": "fighting", "onset_to_alert_ms": "1200"}]
        r = dev_report(self.make(rows), {"z.mp4": 5.0, "n.mp4": 5.0, "x.mp4": 5.0, "m.mp4": 1.0}, 4.0)
        self.assertEqual(r["onset_to_alert_n"], 1)                    # 0 ms counts: zero is a value, not "missing"
        self.assertEqual(r["onset_to_alert_p50_p95"], (0.0, 0.0))
        self.assertEqual((r["onset_to_alert_mid_start_n"], r["onset_to_alert_mid_start_p50_p95"]), (1, (1200.0, 1200.0)))
        self.assertEqual(r["timing_warnings"], [])

    def test_negative_timings_warned(self):
        rows = [{"clip": "a.mp4", "label": "fighting", "pred": "fighting", "onset_to_alert_ms": "-300", "onset_to_gate_ms": "-500"}]
        r = dev_report(self.make(rows), {"a.mp4": 5.0}, 4.0)
        self.assertEqual(r["onset_to_alert_n"], 0)
        self.assertEqual(len(r["timing_warnings"]), 2)

    def test_stored_empty_warnings_kept(self):
        rows = [{"clip": "a.mp4", "label": "fighting", "pred": "fighting", "onset_to_gate_ms": "-500"}]
        r = dev_report(self.make(rows, {"timing_warnings": []}), {"a.mp4": 5.0}, 4.0)
        self.assertEqual(r["timing_warnings"], [], "the pass's own (empty) list is not replaced")

    def test_unknown_label(self):
        rows = [{"clip": "a.mp4", "label": "fighting", "pred": "explosion"}]
        r = dev_report(self.make(rows, {"macro_f1": 0.0}), {}, 4.0)
        self.assertEqual(r["fixed"]["confusion"]["fighting"]["<other>"], 1)

    def test_num(self):
        for x, want in (("0", 0.0), (0, 0.0), ("", None), (None, None), ("None", None), ("nan", None), ("1.5", 1.5),
                        ("x", None), (True, None)):
            self.assertEqual(num(x), want, x)


class ArbiterStats(unittest.TestCase):
    def arb(self, fn=lambda r: time.sleep(0.02), **kw):
        from app.models import Arbiter
        a = Arbiter(fn, **kw); a.start(); return a

    def idle(self, a):
        t = time.time()
        while (a.waiting() or a.running) and time.time() - t < 5:
            time.sleep(0.01)
        time.sleep(0.02)

    def test_empty_stats_serialise(self):
        a = self.arb()
        st = a.stats(window=60)
        a.stop()
        json.dumps(st)
        self.assertEqual(st["dropped_stale"], 0)
        self.assertEqual(a.duty(), 0.0)

    def test_one_request(self):
        a = self.arb()
        a.submit({"prio": 1, "cam": "cam1"}); self.idle(a); a.stop()
        st = a.stats(window=60)
        json.dumps(st)
        self.assertEqual(st["by_priority"]["P1"]["n"], 1)
        self.assertIn("cam1", st["by_camera"])

    def test_endpoint_payload_serialises(self):
        # What GET /api/arbiter returns: arbiter stats + the second-look log + re-look records (tuples, sets of ids).
        a = self.arb()
        for p in (1, 3, 4):
            a.submit({"prio": p, "cam": "cam1"})
        self.idle(a); a.stop()
        held_log = [("cam1", "unverified:detector_blind", 1.0), ("cam1", "reclassified:1->2", 2.0)]
        relooks = [("cam1", "fighting", 0.8, 2.0)]
        body = a.stats(window=60) | {"held_log": [list(x) for x in held_log], "relooks": [list(x) for x in relooks]}
        self.assertEqual(json.loads(json.dumps(body))["held_log"][1][1], "reclassified:1->2")

    def test_duty_thread_safe(self):
        a = self.arb(lambda r: time.sleep(0.001))
        errs, stop = [], threading.Event()

        def read():
            while not stop.is_set():
                try:
                    a.duty(); a.stats(window=60)
                except Exception as e:      # deque mutated during iteration, before the fix
                    errs.append(e); return
        ts = [threading.Thread(target=read) for _ in range(3)]
        for t in ts:
            t.start()
        for k in range(200):
            a.submit({"prio": 3, "cam": f"cam{k % 3}"})
        self.idle(a); stop.set()
        for t in ts:
            t.join()
        a.stop()
        self.assertEqual(errs, [])
        self.assertGreaterEqual(a.duty(), 0.0)


if __name__ == "__main__":
    unittest.main()
