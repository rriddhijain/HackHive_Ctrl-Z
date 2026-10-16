"""Accuracy metrics for clip-level benchmark rows (SPEC §12). Two modes, kept apart so a dev diagnostic can never be
read as the final target:

  observed(rows)  OBSERVED-LABEL diagnostic: macro F1 over the labels that appear as a truth or a prediction in these
                  rows (the historical `macro_f1`, e.g. 0.641 on ab_p5_dev). Comparable only with itself.
  fixed(rows)     FIXED-LABEL evaluation over the 8 canonical labels (app.vlm.CATS, the one place they are defined):
                  per-class support/TP/FP/FN/precision/recall/F1 with zero-support classes listed, macro F1 over the
                  supported classes and over all 8, weighted F1, incident-vs-normal precision/recall, confusion matrix,
                  and `final_metric_valid`: true only on a test split with every class supported, no test clip used for
                  tuning, and run metadata present (NFR-2 target: macro F1 >= 0.75 on the held-out test set).

Rows are dicts with at least "clip", "label" (truth) and "pred". Pure functions, stdlib only.
"""
import hashlib
import json
import platform
import subprocess
import time
from pathlib import Path

from app.vlm import CATS

LABELS = list(CATS)            # the 8 canonical labels, in SPEC §6.2 tie-break order; "normal" last
INCIDENT = [c for c in LABELS if c != "normal"]


def _prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else None
    r = tp / (tp + fn) if tp + fn else None
    f1 = 2 * tp / (2 * tp + fp + fn) if tp + fp + fn else None
    return p, r, f1


def _r(x, n=3):
    return None if x is None else round(x, n)


def per_class(rows, labels):
    out = []
    for L in labels:
        tp = sum(r["label"] == L and r["pred"] == L for r in rows)
        fp = sum(r["label"] != L and r["pred"] == L for r in rows)
        fn = sum(r["label"] == L and r["pred"] != L for r in rows)
        p, rc, f1 = _prf(tp, fp, fn)
        out.append({"label": L, "support": tp + fn, "tp": tp, "fp": fp, "fn": fn,
                    "precision": _r(p), "recall": _r(rc), "f1": _r(f1)})
    return out


def observed(rows):
    """Historical metric, unchanged: mean F1 over sorted(labels seen as truth or prediction). A label that was
    predicted but has no truth rows scores F1 0 and is counted (that is how 0.641 comes about)."""
    labs = sorted({r["label"] for r in rows} | {r["pred"] for r in rows})
    pc = per_class(rows, labs)
    f1s = [c["f1"] if c["f1"] is not None else 1.0 for c in pc]   # same convention as the original score()
    return {"observed_label_macro_f1": round(sum(f1s) / len(f1s), 3) if f1s else None, "observed_labels": labs,
            "observed_per_class": pc}


def confusion(rows, labels=LABELS):
    """{truth: {pred: count}} over the fixed labels; any off-list label lands in '<other>' so nothing is dropped."""
    keys = list(labels) + ["<other>"]
    m = {t: dict.fromkeys(keys, 0) for t in keys}
    for r in rows:
        t = r["label"] if r["label"] in labels else "<other>"
        p = r["pred"] if r["pred"] in labels else "<other>"
        m[t][p] += 1
    if not any(m["<other>"].values()) and not any(m[t]["<other>"] for t in keys):
        m.pop("<other>")
        for t in m:
            m[t].pop("<other>")
    return m


def fixed(rows, split=None, tuned_clips=(), meta=None, labels=LABELS):
    """Fixed-label evaluation. split: 'dev' / 'test' / None (unknown); tuned_clips: clip names used for any tuning;
    meta: run metadata dict (None = missing)."""
    pc = per_class(rows, labels)
    sup = [c for c in pc if c["support"] > 0]
    zero = [c["label"] for c in pc if c["support"] == 0]
    f1_sup = [c["f1"] for c in sup]
    f1_all = [c["f1"] if c["f1"] is not None else 0.0 for c in pc]   # an unsupported class counts as 0 (it has no evidence)
    n = sum(c["support"] for c in pc)
    weighted = sum(c["f1"] * c["support"] for c in sup) / n if n else None
    inc = lambda x: x != "normal"
    tp = sum(inc(r["label"]) and inc(r["pred"]) for r in rows)
    n_true, n_pred = sum(inc(r["label"]) for r in rows), sum(inc(r["pred"]) for r in rows)
    leaked = sorted({r["clip"] for r in rows} & set(tuned_clips))
    reasons = []
    if split != "test":
        reasons.append(f"split is {split or 'unknown'}, not test")
    if zero:
        reasons.append("no test support for: " + ", ".join(zero))
    if leaked:
        reasons.append("clips used for tuning: " + ", ".join(leaked))
    if not meta:
        reasons.append("run metadata missing")
    return {"labels": list(labels), "n": len(rows), "per_class": pc, "zero_support_classes": zero,
            "macro_f1_supported": _r(sum(f1_sup) / len(f1_sup)) if f1_sup else None,
            "supported_classes": [c["label"] for c in sup],
            "macro_f1_all8": _r(sum(f1_all) / len(f1_all)),
            "weighted_f1": _r(weighted),
            "incident_precision": _r(tp / n_pred) if n_pred else None,
            "incident_recall": _r(tp / n_true) if n_true else None,
            "confusion": confusion(rows, labels),
            "split": split, "final_metric_valid": not reasons, "final_metric_invalid_reasons": reasons}


def git(*args, cwd=None):
    try:
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=5).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def run_meta(root, cfg_path, tag, split, model, repetitions=1, extra=None):
    """Who/what/where for a benchmark run: commit, dirty tree, config hash, model, machine, time, tag, split, reps.
    The model digest is asked from Ollama when it answers (local only, 2 s timeout), else null."""
    digest = None
    try:
        import httpx
        from app.config import CFG
        r = httpx.post(CFG["vlm"]["base_url"] + "/api/show", json={"model": model}, timeout=2)
        if r.status_code == 200:
            j = r.json()
            digest = j.get("digest") or (j.get("details") or {}).get("parent_model") or None
            digest = digest or hashlib.sha256(json.dumps(j.get("details", {}), sort_keys=True).encode()).hexdigest()[:16]
    except Exception:
        pass
    return {"tag": tag, "split": split, "repetitions": repetitions,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "epoch": time.time(),
            "commit": git("rev-parse", "HEAD", cwd=root), "dirty": bool(git("status", "--porcelain", cwd=root)),
            "config_sha256": hashlib.sha256(Path(cfg_path).read_bytes()).hexdigest()[:16] if Path(cfg_path).exists() else None,
            "model": model, "model_digest": digest,
            "machine": {"platform": platform.platform(), "machine": platform.machine(), "processor": platform.processor(),
                        "python": platform.python_version(), "node": platform.node()},
            **(extra or {})}
