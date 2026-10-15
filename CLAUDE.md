# CLAUDE.md

Local AI video incident detection for the Honeywell hackathon (PS3). **SPEC.md is the contract**: read it before changing any interface. PLAN.md = schedule/phases, DECISIONS.md = why + decision log.

## Ground rules
- Claude builds everything; the team validates. Build in the phases of PLAN.md; each phase ends with self-checks passing + a "what to test" note.
- SPEC §6–§11 (categories, contracts, DB, API, config, layout) change only with captain approval + version bump + DECISIONS log entry.
- No downloads/installs without the captain's confirmation (D21).
- Open-weight models only, run locally; no cloud APIs, no API keys, no CDNs; must work offline.
- Stdlib and already-installed deps first. No abstraction with one implementation.
- Every timestamp is epoch seconds (`time.time()`); IST only at display/parse time.
- One coordinate system: pixels of the 640 px-wide frame for boxes, track histories, zones, gates, hints and crops. Zones are fractions only in `config.yaml` (D54).
- Gates take person tracks only (`Detector.person_hists()`). Images for the VLM are letterboxed, never stretched (D44).
- Latency is quoted as onset-to-alert (what a judge times), never the model-only number alone (D50).
- Every module has a runnable self-check: `uv run python -m app.<module>`.
- Never commit videos, weights or `data/` (gitignored).

## Layout
`app/` pipeline (config, ingest, detect, gate, scheduler, models, vlm, events, db, chat, server, pipeline) · `web/` React dashboard · `bench/` benchmarks · `scripts/` tooling · `models/` weights (gitignored) · `data/` videos, DB, frames (gitignored).

## Run
- `uv run python -m app.preview` live camera grid with YOLO boxes (P1 validation)
- `uv run python scripts/list_cameras.py` list camera indices / test a stream URL
- `uv run python -m bench.latency_test` model latency + contention test
- `uv run python -m app.pipeline <clip> [...]` full pipeline on clips: alerts, per-clip right/wrong, onset-to-alert ms, GPU duty (labels from `bench/labels.csv`)
