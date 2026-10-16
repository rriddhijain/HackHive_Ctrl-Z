"""Benchmark data validation (P8 hygiene). Exit 1 on invalid data; a missing-data report either way.

  uv run python -m bench.validate                 labels.csv + clip files + results files
  uv run python -m bench.validate --json out.json also write the report (bench/results/benchmark_metadata.json is the
                                                  committed snapshot: asset inventory + what the data can/can't measure)

Errors (exit 1): a labels.csv row without a file, a clip labelled twice (or with two different labels), a label outside
the 8 canonical labels (bench/metrics.LABELS), a split other than train/dev/test, a clip in test AND train/dev, a
negative onset or one past the clip's end, a results row whose clip has no label, a test clip found in a tuning input
(any result file that is not ab_test_*: dev passes, A/Bs, gate checks are where thresholds were tuned).
Historical rows for clips that lost their label are accepted only when listed in bench/unlabelled_rows.csv with a
reason (explicitly marked, never silently). Warnings (exit 0): label files in data/ with no labels.csv row (unlabelled, never scored), labelled clips whose file
is missing from this clone (videos are gitignored), and the coverage report: per split and class, clips and minutes.
Nothing here creates labels: missing categories are reported, never filled in.
"""
import argparse
import csv
import io
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from bench.metrics import LABELS

ROOT = Path(__file__).resolve().parents[1]
SPLITS = ("train", "dev", "test")
VIDEO = (".mp4", ".avi", ".mov", ".mkv")
NORMAL_MIN_TARGET = 30.0      # minutes of normal/look-alike footage needed for false alarms per camera-hour (SPEC §12)


def duration_s(path):
    try:
        import cv2
        cap = cv2.VideoCapture(str(path))
        n, fps = cap.get(cv2.CAP_PROP_FRAME_COUNT), cap.get(cv2.CAP_PROP_FPS)
        return round(n / fps, 2) if n and fps else None
    except Exception:
        return None


def find_files(data):
    """clip file name -> [paths] under data/dev, data/test, data/train, data/demo (duplicates reported)."""
    out = defaultdict(list)
    for sub in ("dev", "test", "train", "demo"):
        for p in sorted((data / sub).glob("**/*")):
            if p.suffix.lower() in VIDEO:
                out[p.name].append(p)
    return out


def validate(root=ROOT, labels_csv=None, results_dir=None, data=None, require_files=True):
    labels_csv = Path(labels_csv or root / "bench" / "labels.csv")
    results_dir = Path(results_dir or root / "bench" / "results")
    data = Path(data or root / "data")
    errors, warnings = [], []
    rows = list(csv.DictReader(io.StringIO(Path(labels_csv).read_text(), newline=''))) if labels_csv.exists() else []
    if not rows:
        errors.append(f"{labels_csv}: no label rows")
    files = find_files(data)
    by_clip = defaultdict(list)
    for i, r in enumerate(rows, start=2):
        by_clip[Path(r["clip"]).name].append((i, r))
    clips = {}
    for clip, rs in by_clip.items():
        if len(rs) > 1:
            labs = {r["label"] for _, r in rs}
            errors.append(f"{clip}: {len(rs)} rows (lines {', '.join(str(i) for i, _ in rs)})"
                          + (f" with different labels {sorted(labs)}" if len(labs) > 1 else ""))
        line, r = rs[0]
        lab, split = r["label"].strip(), (r.get("split") or "").strip()
        if lab not in LABELS:
            errors.append(f"{clip} (line {line}): label {lab!r} is not one of the 8 canonical labels")
        if split not in SPLITS:
            errors.append(f"{clip} (line {line}): split {split!r} is not train/dev/test")
        if len({(x.get('split') or '').strip() for _, x in rs}) > 1:
            errors.append(f"{clip}: listed in more than one split")
        paths = files.get(clip, [])
        if len(paths) > 1:
            warnings.append(f"{clip}: {len(paths)} files with this name: {[str(p.relative_to(root)) for p in paths]}")
        dur = duration_s(paths[0]) if paths else None
        if not paths:
            (errors if require_files else warnings).append(f"{clip}: labelled but no file under data/ (videos are gitignored)")
        on = (r.get("onset_s") or "").strip()
        if on:
            try:
                v = float(on)
                if v < 0:
                    errors.append(f"{clip}: onset_s {v} is negative")
                elif dur is not None and v > dur:
                    errors.append(f"{clip}: onset_s {v} is past the clip end ({dur} s)")
            except ValueError:
                errors.append(f"{clip}: onset_s {on!r} is not a number")
        elif lab not in ("normal",) and lab in LABELS:
            warnings.append(f"{clip}: incident clip without onset_s (onset -> alert can't be measured)")
        clips[clip] = {"label": lab, "split": split, "file": str(paths[0].relative_to(root)) if paths else None,
                       "duration_s": dur, "onset_s": float(on) if on and on.replace('.', '', 1).lstrip('-').isdigit() else None}
    for name, paths in files.items():
        if name not in clips:
            warnings.append(f"{name}: video under data/ with no labels.csv row (unlabelled: never scored)")
    # results: every row must name a labelled clip; a test clip must not appear in any tuning input
    marked = {(r["results_file"], r["clip"]): r for r in csv.DictReader(io.StringIO(Path(root / "bench" / "unlabelled_rows.csv").read_text(), newline=''))} \
        if (root / "bench" / "unlabelled_rows.csv").exists() else {}
    test = {c for c, x in clips.items() if x["split"] == "test"}
    tuning_hits = defaultdict(set)
    for f in sorted(results_dir.glob("*.csv")):
        rs = list(csv.DictReader(io.StringIO(Path(f).read_text(), newline='')))
        if not rs or "clip" not in rs[0]:
            continue
        for r in rs:
            c = Path(r["clip"]).name
            if c not in clips:
                if (f.name, c) in marked:
                    warnings.append(f"{f.name}: {c} has no label now; explicitly marked in bench/unlabelled_rows.csv "
                                    f"(recorded label {marked[(f.name, c)]['recorded_label']!r})")
                else:
                    errors.append(f"{f.name}: row for {c!r}, which has no label (unlabelled benchmark row; mark it in "
                                  "bench/unlabelled_rows.csv with a reason, or label it)")
            elif "label" in r and r["label"] and r["label"] != clips[c]["label"]:
                warnings.append(f"{f.name}: {c} recorded with label {r['label']!r}, labels.csv now says {clips[c]['label']!r}")
            if c in test and not f.name.startswith("ab_test_"):
                tuning_hits[c].add(f.name)
    for f in sorted(results_dir.glob("gate_check*.txt")):
        for c in test:
            if c in f.read_text():
                tuning_hits[c].add(f.name)
    for c, fs in tuning_hits.items():
        errors.append(f"{c}: test clip appears in tuning inputs {sorted(fs)}")
    # coverage: what the data can and cannot measure
    cov = {sp: {lab: {"clips": 0, "minutes": 0.0} for lab in LABELS} for sp in SPLITS}
    for c, x in clips.items():
        if x["split"] in cov and x["label"] in LABELS:
            cov[x["split"]][x["label"]]["clips"] += 1
            cov[x["split"]][x["label"]]["minutes"] = round(cov[x["split"]][x["label"]]["minutes"] + (x["duration_s"] or 0) / 60, 2)
    missing = {sp: [lab for lab in LABELS if cov[sp][lab]["clips"] == 0] for sp in SPLITS}
    normal_min = round(sum(cov[sp]["normal"]["minutes"] for sp in SPLITS), 2)
    report = {"labels_csv": str(labels_csv.relative_to(root)) if labels_csv.is_relative_to(root) else str(labels_csv),
              "n_labelled": len(clips), "splits": dict(Counter(x["split"] for x in clips.values())),
              "coverage": cov, "classes_without_clips": missing,
              "normal_minutes": normal_min, "normal_minutes_target": NORMAL_MIN_TARGET,
              "final_metric_possible": not missing["test"] and normal_min >= NORMAL_MIN_TARGET and not errors,
              "clips": clips, "errors": errors, "warnings": warnings}
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json"); ap.add_argument("--allow-missing-files", action="store_true",
                                               help="a labelled clip missing from data/ is a warning (clean clone)")
    a = ap.parse_args()
    r = validate(require_files=not a.allow_missing_files)
    print(f"{r['n_labelled']} labelled clips, splits {r['splits']}")
    for sp in SPLITS:
        have = {lab: v for lab, v in r["coverage"][sp].items() if v["clips"]}
        print(f"  {sp:<5} " + (", ".join(f"{lab} {v['clips']} ({v['minutes']} min)" for lab, v in have.items()) or "no clips")
              + (f"   MISSING: {', '.join(r['classes_without_clips'][sp])}" if have else ""))
    print(f"  normal footage {r['normal_minutes']} min (target >= {NORMAL_MIN_TARGET} min for false alarms per camera-hour)")
    print(f"  final 8-label test metric possible: {r['final_metric_possible']}")
    for w in r["warnings"]:
        print("WARNING", w)
    for e in r["errors"]:
        print("ERROR  ", e)
    if a.json:
        Path(a.json).write_text(json.dumps(r, indent=1))
    print("validation", "FAILED" if r["errors"] else "ok")
    sys.exit(1 if r["errors"] else 0)


if __name__ == "__main__":
    main()
