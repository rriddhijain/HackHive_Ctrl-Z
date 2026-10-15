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
uv sync              # Python 3.12 environment
ollama pull qwen3.5:4b
./run_demo.sh        # starts everything, opens the dashboard
```
