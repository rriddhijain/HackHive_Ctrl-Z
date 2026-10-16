"""Metric modes (bench/metrics.py) and the benchmark score (bench/ab.py score()).
Run: uv run python -m unittest discover -s tests -t ."""
import csv
import io
import tempfile
import unittest
from pathlib import Path

from bench import metrics
from bench.metrics import LABELS

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "bench" / "results"


def rows(name):
    return list(csv.DictReader(io.StringIO(Path(RES / name).read_text(encoding="utf-8"), newline='')))


class Labels(unittest.TestCase):
    def test_labels_match_the_model_categories(self):
        try:
            from app.vlm import CATS
        except ImportError as e:                                      # app.vlm needs OpenCV
            self.skipTest(f"app.vlm not importable here: {e}")
        self.assertEqual(LABELS, CATS)

    def test_metrics_and_validate_load_without_opencv(self):
        import subprocess, sys
        code = "import sys; import bench.metrics, bench.validate, bench.ab; sys.exit('cv2' in sys.modules or 'ultralytics' in sys.modules)"
        self.assertEqual(subprocess.run([sys.executable, "-c", code], cwd=ROOT).returncode, 0)


class Historical(unittest.TestCase):
    def test_p5_dev_still_0641(self):
        r = rows("ab_p5_dev.csv")
        self.assertEqual(len(r), 11)
        o = metrics.observed(r)
        self.assertEqual(o["observed_label_macro_f1"], 0.641)
        self.assertEqual(o["observed_labels"], ["fighting", "normal", "person_down"])
        f1 = {c["label"]: c["f1"] for c in o["observed_per_class"]}
        self.assertEqual(f1, {"fighting": 0.923, "normal": 1.0, "person_down": 0.0})

    def test_p6_and_p6b_also_0641(self):
        for name in ("ab_dev_p6.csv", "ab_dev_p6b.csv"):
            self.assertEqual(metrics.observed(rows(name))["observed_label_macro_f1"], 0.641, name)

    def test_score_keeps_historical_key(self):
        from bench.ab import score
        r = rows("ab_p5_dev.csv")
        for x in r:   # csv gives strings; score() reads these as numbers or None
            for k in ("start_to_alert_ms", "trigger_to_alert_ms", "onset_to_alert_ms"):
                x[k] = float(x[k]) if x.get(k) else None
            x["onset_s"] = None
        s = score(r, split="dev")
        self.assertEqual(s["macro_f1"], 0.641)
        self.assertEqual(s["observed_label_macro_f1"], 0.641)
        self.assertFalse(s["fixed"]["final_metric_valid"])


class Fixed(unittest.TestCase):
    def test_missing_classes_exposed(self):
        f = metrics.fixed(rows("ab_p5_dev.csv"), split="dev")
        self.assertEqual(f["labels"], LABELS)
        self.assertEqual(len(f["per_class"]), 8)
        self.assertEqual(sorted(f["zero_support_classes"]),
                         sorted(["person_down", "fire_smoke", "crowd_incident", "tailgating", "property_damage",
                                 "suspicious_activity"]))
        self.assertEqual(f["supported_classes"], ["fighting", "normal"])
        self.assertEqual(f["macro_f1_supported"], round((0.923 + 1.0) / 2, 3))
        self.assertEqual(f["macro_f1_all8"], round((0.923 + 1.0) / 8, 3))   # 6 classes without evidence count 0
        self.assertFalse(f["final_metric_valid"])
        self.assertTrue(any("not test" in x for x in f["final_metric_invalid_reasons"]))
        self.assertTrue(any("no test support" in x for x in f["final_metric_invalid_reasons"]))

    def test_zero_support_reported_not_omitted(self):
        f = metrics.fixed([{"clip": "a", "label": "normal", "pred": "normal"}], split="test", meta={"x": 1})
        pd = next(c for c in f["per_class"] if c["label"] == "person_down")
        self.assertEqual((pd["support"], pd["tp"], pd["fp"], pd["fn"], pd["f1"]), (0, 0, 0, 0, None))
        self.assertIn("person_down", f["zero_support_classes"])
        self.assertFalse(f["final_metric_valid"])

    def test_perfect_eight_class(self):
        r = [{"clip": f"{c}.mp4", "label": c, "pred": c} for c in LABELS]
        f = metrics.fixed(r, split="test", tuned_clips=(), meta={"commit": "x"})
        self.assertEqual(f["macro_f1_all8"], 1.0)
        self.assertEqual(f["macro_f1_supported"], 1.0)
        self.assertEqual(f["weighted_f1"], 1.0)
        self.assertEqual((f["incident_precision"], f["incident_recall"]), (1.0, 1.0))
        self.assertTrue(f["final_metric_valid"], f["final_metric_invalid_reasons"])
        self.assertEqual(metrics.observed(r)["observed_label_macro_f1"], 1.0)

    def test_tuned_or_unmetadata_test_is_invalid(self):
        r = [{"clip": f"{c}.mp4", "label": c, "pred": c} for c in LABELS]
        self.assertFalse(metrics.fixed(r, "test", tuned_clips={"normal.mp4"}, meta={"a": 1})["final_metric_valid"])
        self.assertFalse(metrics.fixed(r, "test", meta=None)["final_metric_valid"])

    def test_fighting_read_as_person_down(self):
        r = [{"clip": "a", "label": "fighting", "pred": "fighting"}, {"clip": "b", "label": "fighting", "pred": "person_down"},
             {"clip": "c", "label": "normal", "pred": "normal"}]
        f = metrics.fixed(r, split="dev")
        self.assertEqual(f["confusion"]["fighting"]["person_down"], 1)
        self.assertEqual(f["confusion"]["fighting"]["fighting"], 1)
        fi = next(c for c in f["per_class"] if c["label"] == "fighting")
        pd = next(c for c in f["per_class"] if c["label"] == "person_down")
        self.assertEqual((fi["tp"], fi["fn"], fi["recall"]), (1, 1, 0.5))
        self.assertEqual((pd["support"], pd["fp"], pd["precision"]), (0, 1, 0.0))
        self.assertEqual((f["incident_recall"], f["incident_precision"]), (1.0, 1.0))   # still an incident card

    def test_off_list_label_not_dropped(self):
        f = metrics.fixed([{"clip": "a", "label": "fighting", "pred": "explosion"}], split="dev")
        self.assertEqual(f["confusion"]["fighting"]["<other>"], 1)


class Validate(unittest.TestCase):
    def _write(self, d, labels, results=None):
        (d / "bench" / "results").mkdir(parents=True)
        (d / "data" / "dev").mkdir(parents=True)
        with open(d / "bench" / "labels.csv", "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh); w.writerow(["clip", "label", "split", "onset_s"]); w.writerows(labels)
        for name, rs in (results or {}).items():
            with open(d / "bench" / "results" / name, "w", encoding="utf-8", newline="") as fh:
                w = csv.writer(fh); w.writerow(["clip", "label", "pred"]); w.writerows(rs)

    def run_v(self, labels, results=None):
        from bench.validate import validate
        with tempfile.TemporaryDirectory() as t:
            d = Path(t); self._write(d, labels, results)
            return validate(root=d, require_files=False)

    def test_errors(self):
        r = self.run_v([["a.mp4", "fighting", "dev", "-1"], ["a.mp4", "normal", "test", ""], ["b.mp4", "explosion", "dev", ""],
                        ["c.mp4", "normal", "holdout", ""], ["t.mp4", "fighting", "test", "1"]],
                       {"ab_dev_x.csv": [["t.mp4", "fighting", "fighting"], ["zzz.mp4", "normal", "normal"]]})
        e = "\n".join(r["errors"])
        for needle in ("a.mp4: 2 rows", "different labels", "more than one split", "negative", "explosion",
                       "holdout", "zzz.mp4", "t.mp4: test clip appears in tuning inputs"):
            self.assertIn(needle, e)

    def test_missing_classes_reported_not_invented(self):
        r = self.run_v([["a.mp4", "fighting", "dev", "0"], ["b.mp4", "normal", "dev", ""]])
        self.assertEqual(r["errors"], [])
        self.assertIn("person_down", r["classes_without_clips"]["dev"])
        self.assertEqual(r["classes_without_clips"]["test"], LABELS)
        self.assertFalse(r["final_metric_possible"])

    def test_non_ascii_files_read_as_utf8(self):
        # Windows' default code page broke validation on these: dashes, curly quotes, accents, emoji in results files.
        text = "en – em — “quoted” ‘single’ café 🚨"
        with tempfile.TemporaryDirectory() as t:
            d = Path(t); self._write(d, [["a.mp4", "fighting", "dev", "1"]])
            with open(d / "bench" / "results" / "ab_dev_u.csv", "w", encoding="utf-8", newline="") as fh:
                w = csv.writer(fh); w.writerow(["clip", "label", "pred", "summary"]); w.writerow(["a.mp4", "fighting", "fighting", text])
            (d / "bench" / "results" / "gate_check_u.txt").write_text(text, encoding="utf-8")
            # Fail on any open()/read_text() of ours that relies on the platform's default encoding.
            code = ("import sys, warnings; warnings.simplefilter('error', EncodingWarning); from pathlib import Path; "
                    "from bench.validate import validate; r = validate(root=Path(sys.argv[1]), require_files=False); "
                    "sys.exit(1 if r['errors'] else 0)")
            import subprocess, sys
            p = subprocess.run([sys.executable, "-X", "warn_default_encoding", "-c", code, t], cwd=ROOT,
                               capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(p.returncode, 0, p.stderr[-2000:])

    def test_repo_labels_valid(self):
        from bench.validate import validate
        r = validate(require_files=False)
        self.assertEqual(r["errors"], [], r["errors"])


if __name__ == "__main__":
    unittest.main()
