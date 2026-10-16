# HackHive Ctrl-Z: Local AI Video Incident Detection

Honeywell hackathon, Problem Statement 3: live video → incident detection + summaries → searchable store → chatbot. Fully local, open-weight models only.

## Start here: which document is for what

| File | Answers | Read it when |
|---|---|---|
| **[SPEC.md](SPEC.md)** | **What** we build: requirements, pipeline, dataflow, contracts, edge cases | You need to know how anything works or should behave. **Single source of truth.** |
| **[PLAN.md](PLAN.md)** | **When / who**: schedule, milestones, who tests what | You want to know what to do right now |
| **[DECISIONS.md](DECISIONS.md)** | **Why**: questions we answered + decision log | You wonder why something was chosen, or want to change it |

**Rule:** if SPEC.md and another file disagree, SPEC.md wins.

## Setup (once the code lands)
```bash
uv sync                      # Python 3.12 environment
ollama pull qwen3.5:4b-mlx   # demo model (D28); qwen3.5:2b is the fallback
./run_demo.sh                # starts everything, opens the dashboard
```

**Demo machine (M5, D47):** same Ollama version as the build Mac; copy `~/.ollama/models` from the build Mac (no internet needed); `uv sync`; grant camera permission; check Continuity Camera with the iPhone 15 (it must use the M5's Apple ID); run once with Wi-Fi off.

**Live fall camera:** the iPhone, mounted ~2 m high and angled down so the floor is in view. The laptop's webcam can't see the floor.

## Benchmarks, metrics and tests
```bash
uv run python -m unittest discover -s tests -t .   # unit + synthetic tests (metrics, validation, second look, scheduler)
uv run python -m bench.validate                    # labels.csv vs clip files vs results; exit 1 on invalid data
uv run python -m bench.ab --gate --check           # gate regression check on the dev clips (CPU, no model)
uv run python -m bench.diagnose                    # detector-only view of every dev clip (CPU, no model)
uv run python -m bench.ab --dev --tag NAME         # the real dev pass: needs Ollama + qwen3.5:4b-mlx + data/dev clips
uv run python -m bench.ab --dev --tag NAME --no-down-guard   # the same with the person_down second look off (D83 A/B)
```
**Two F1 numbers, never mixed.** `macro_f1` / `observed_label_macro_f1` (the historical **0.641**) is an
**observed-label dev diagnostic**: the mean over the labels that appear in the rows. The `fixed` block is the 8-label
evaluation with every class listed (zero-support ones included); `final_metric_valid` is true only on a test split with
all 8 classes supported, no test clip used for tuning, and run metadata. Today it is false: no test split, 6 of 8
classes have no clips (REPORT.md section 11).

**Not in git** (gitignored): `data/` (dev and demo videos, DB, key frames) and `models/` (YOLO weights); the Ollama
model lives in `~/.ollama/models`. Copy them from the dev Mac. Exact versions: `shasum -a 256 models/*.pt`,
`ollama show qwen3.5:4b-mlx`; every dev pass records commit, config hash, model digest and machine in its summary JSON
(`bench/results/benchmark_metadata.json` is the asset snapshot). A clean clone can run the tests, `bench.validate
--allow-missing-files` and the frontend build; anything with video needs `data/`.

## Current status
P0 (model lock) and P1 (cameras + YOLO tracking) are built; SPEC is at v1.6 (judge-review package D42–D56). P2 onwards follows [PLAN.md](PLAN.md).
