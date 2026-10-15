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

## Current status
P0 (model lock) and P1 (cameras + YOLO tracking) are built; SPEC is at v1.6 (judge-review package D42–D56). P2 onwards follows [PLAN.md](PLAN.md).
