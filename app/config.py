"""Loads config.yaml (SPEC §10) into a plain dict. One global CFG; tests may call load() with another path."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def load(path=ROOT / "config.yaml"):
    cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    for cam in cfg["cameras"]:
        cam.setdefault("door_zone", None)
        cam.setdefault("watch_zone", None)
    return cfg


CFG = load()

if __name__ == "__main__":
    assert CFG["detector"]["fps"] > 0 and CFG["cameras"], "config needs a detector fps and at least one camera"
    print(f"config ok: {len(CFG['cameras'])} cameras, model {CFG['vlm']['model']}, detector {CFG['detector']['model']}")
