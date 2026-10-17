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
- Any gate or threshold change (`app/gate.py`, `app/scheduler.py`, `gate:`/`detector:` in `config.yaml`) must pass `uv run python -m bench.ab --gate --check` (D72). Thresholds are tuned on the dev clips only and judged on the test split (P8).
- Never commit videos, weights or `data/` (gitignored).

## Layout
`app/` pipeline (config, ingest, detect, gate, scheduler, models, vlm, events, db, chat, server, pipeline) · `web/` React dashboard · `firmware/esp32/` ESP32 guard console (D89) · `bench/` benchmarks · `scripts/` tooling · `models/` weights (gitignored) · `data/` videos, DB, frames (gitignored).

## Run
- `uv run python -m app.preview` live camera grid with YOLO boxes (P1 validation)
- `uv run python scripts/list_cameras.py` list camera indices / test a stream URL
- `uv run python -m bench.latency_test` model latency + contention test
- `cd web && npm run build` (Next.js static export → `web/dist`) then `uv run python -m app.server` dashboard at http://localhost:8000: boots in Clips mode with nothing running; six tabs Clips, Live, Alerts, Ask, Pipeline, Report (`--selfcheck` for the self-check)
- `cd web && npm run typecheck` TypeScript check · `npm run dev` hot-reload UI on :3000 (needs the API on :8000 for data) · `npm run theme` regenerate M3 colour tokens from the seed
- `uv run python -m scripts.seed_history` seeded demo history for chat (`--remove` deletes it) · `uv run python -m bench.chat_runner` chat question runner (30 questions, temp DB)
- `uv run python -m app.console --board` ESP32 console check on the real board (press BOOT twice); flashing: `firmware/esp32/README.md`
- `uv run python -m app.whatsapp` WhatsApp alerts self-check (fake endpoint) · `--test` sends one real message (needs `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `WHATSAPP_TO` in the environment; D90)
- `uv run python -m bench.ab --gate --check` gate regression check on every dev clip (CPU, ~45 s, exit 1 on failure)
- `uv run python -m unittest discover -s tests -t .` unit + synthetic tests · `uv run python -m bench.validate` benchmark data checks (exit 1 on invalid) · `uv run python -m bench.diagnose` detector-only view of the dev clips
- Two F1s (D87): `observed_label_macro_f1` (= historical `macro_f1`, dev diagnostic) vs the `fixed` 8-label block; only `fixed.final_metric_valid` may be quoted as the NFR-2 result
- `uv run python -m app.pipeline <clip> [...]` full pipeline on clips: alerts, per-clip right/wrong, onset-to-alert ms, GPU duty (labels from `bench/labels.csv`)
