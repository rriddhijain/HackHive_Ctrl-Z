# HackHive - Round-1 pitch deck (Honeywell PS3)

Fri 16 Oct 2026. A 6-7 minute talk by the team, then the live demo (docs/DEMO_SCRIPT.md). Plain markdown, one `## Slide` per slide.

Rules for this deck:
- Every number on a slide appears in REPORT.md and carries its section. Nothing is quoted from a plan, a decision log or memory.
- Every REPORT.md number was measured on the dev machine M4 (Apple M4, 16 GB); nothing has been re-measured on the demo machine M5 yet (REPORT.md header, §1).
- `<<...>>` placeholders are copied from REPORT.md verbatim; the author fills both files.
- Model and part names (Qwen3.5, Gemma 4, LFM2.5-VL, YOLO26n, ESP32) are names, not measurements.

## Slide 1 - The problem: one control room, too many cameras

- One operator, a wall of feeds; the incident is found on playback, late.
- Fights, falls, fires: seconds matter; review takes minutes.
- Cloud video AI: footage leaves the site, needs keys, stops when the link drops.
- On-prem security wants the alert on-site, now, on its own hardware.
- Our answer: one laptop, open-weight local models, an alert while it is happening.

Speaker notes: Honeywell's customers run control rooms where one person watches many feeds, and most incidents are found when someone reviews the footage afterwards. Cloud video analytics is a non-starter for an on-prem security site: footage leaves the building, an API key becomes a dependency, and an outage stops the alerts. Everything you will see today runs on the laptop in front of you.

Source: no numbers on this slide.

## Slide 2 - Our approach: a cheap gate decides WHEN, a local VLM decides WHAT

- YOLO26n person detector at 10 fps per camera, on CPU: the always-on gate.
- Gate rules on person tracks (contact + speed, fast drop) decide when to ask.
- Qwen3.5-4B via Ollama sees one 2x2 letterboxed mosaic: 4 frames spanning 2 s.
- Streaming JSON verdict: category, probabilities, summary; alert at the category token.
- Verdicts become events in SQLite; the chat answers only with cited stored events.

Speaker notes: A vision-language model on every frame does not fit on a laptop, so an always-on detector and a few rules on person tracks decide when the model should look at all. The model sees four recent frames as one letterboxed mosaic and streams back structured JSON; the alert goes out the moment the category token arrives, before the summary is finished. Every verdict is stored as an event, and the chat is only allowed to talk about those events.

Source: REPORT.md §1 (YOLO26n, 10 fps, Qwen3.5-4B as qwen3.5:4b-mlx via Ollama, 2x2 letterboxed mosaic, 4 frames spanning 2 s). CPU and the gate rules are design facts (SPEC.md §5), not numbers.

## Slide 3 - Architecture: one pipeline, every stage timed

- Capture (latest frame only) -> YOLO + ByteTrack -> gates + change-gated baselines.
- One arbiter: priority queue, gate-triggered calls first, stale requests dropped.
- Streaming VLM -> cross-check veto -> early alert at the category token.
- Events: SQLite + FTS5 + key frames -> FastAPI -> SSE -> React dashboard.
- Chat: rules -> SQL/FTS5 -> template, or model answer with citation check.
- One coordinate system end to end; every stage timed in the Pipeline view.

Speaker notes: Each camera keeps only its latest frame, runs the detector on the CPU and feeds person tracks to the gate rules; a change-gated baseline timer covers what the gates cannot see. One arbiter owns the single GPU: gate-triggered calls go first and stale requests are dropped, so a fight on one camera never waits behind a routine look at an empty corridor. The alert leaves as soon as the category token streams in; the full JSON, the event store, the dashboard and the chat come after it.

Source: no numbers on this slide (architecture as in SPEC.md §5).

## Slide 4 - Live demo plan: three acts, and what to watch

- Act 1, clips: v011.avi fight alerts; sample_bus.mp4 ends with "No incidents".
- Act 1, look-alike p3c_shove_sit_hug.mp4: the shove alerts; the sit and hug do not.
- Act 2, live (webcam + iPhone): a staged shove alerts; a floor-sit does not.
- Act 3, chat: "Show all tailgating events from camera 2 today", then two more.
- Watch for: probability bar, trigger -> alert on the card, Pipeline stage timeline, mosaic, raw JSON.
- Chat answers cite [#id] events: key frame, IST time, camera; a grounded no counts.

Speaker notes: Three acts follow the slides: recorded clips, two live cameras, then the chat; the script and every fallback are in docs/DEMO_SCRIPT.md. Act 3 asks the brief's own example, "Show all tailgating events from camera 2 today", then "What incidents happened in the last 10 minutes?" and "How many falls today?". We quote no numbers on stage: the card shows trigger -> alert, the result tile puts the labelled onset next to the alert time, and REPORT.md has the rest.

Source: clip names as in REPORT.md §3; the questions, including "camera 2" and "10 minutes", as quoted in REPORT.md §7. Act order and fallbacks: docs/DEMO_SCRIPT.md.

## Slide 5 - Measured so far: M4, 11 dev clips, one at a time

- Every figure below is a row in a committed bench/results/ file, via REPORT.md.
- Dev clips only, fights vs normal, no held-out split: optimistic by construction.
- Model-only rows are labelled as such and never quoted as alert latency.

| Measure | Result | Target (SPEC §4) | REPORT.md |
|---|---|---|---|
| Clips right | 10 of 11 | - | §1, §4 |
| Incident recall / precision | 1.00 (7 of 7) / 1.00 | >= 0.85 / >= 0.85 | §4, §2 |
| False alarms on the 4 normal + look-alike clips | 0 | - | §4 |
| Wrong category | 1 (v026: fight read as person_down, still an incident card) | - | §4 |
| Trigger -> alert (7 alerts) | p50 1268 ms, p95 1332 ms | - | §5a |
| Onset-to-alert (n = 1, p3c_shove_sit_hug) | 3216 ms | p95 <= 3000 ms: missed by 216 ms | §5b |
| Model only, not alert latency (P0, qwen3.5:4b-mlx, tile 160) | time to category p50 1.603 s / p95 2.190 s; full call 3.539 / 4.357 s | to-category p95 <= 2.0 s; full call p50 <= 3.7 s, p95 <= 4.1 s | §5c, §5 |
| YOLO per frame (plain yolo26n) | 15.6-19.2 ms | <= 40 ms | §6a |
| GPU duty | 1 clip at a time 0.746 mean; 1 idle camera 53-56 %; 3 static 39 %; 3 busy cameras 91-99.5 % | <= 60 % with 3 cameras: missed | §5e |
| Chat runner, seeded history | 44 of 44 right; 0 invented events; 0 uncited sentences | - | §7 |
| Chat answer time | template p50 0 ms, p95 1 ms; model summaries p50 3116 ms, max 6035 ms | <= 5 s: 1 of 4 model answers over | §7 |
| Cold start, ./run_demo.sh | M4: 10.2 s; M5: pending | < 2 min | §8 |
| Store -> card | p50 13.0 ms / p95 20.2 ms (n = 2) | - | §5d |

Speaker notes: Ten of eleven dev clips right, every incident caught, no false alarm on the four normal and look-alike clips; the one error is a fight read as a person down, still an incident card. Trigger -> alert sits at p50 1268 ms; the single onset-labelled clip gives 3216 ms onset-to-alert, 216 ms over the target on one sample, and most of that delay is the gate (1.9 s), not the trigger -> alert path (1.3 s). GPU duty misses its target with three busy cameras, which is why the demo plays one clip at a time.

Source: REPORT.md §1, §2 (targets), §4, §5 (model-only targets), §5a, §5b (incl. 1.9 s / 1.3 s), §5c, §5d (placeholder), §5e, §6a, §7, §8 (placeholder, < 2 min). All measured on the M4 (REPORT.md header).

## Slide 6 - Why local, on-prem: built for a Honeywell site

- No cloud, no API keys, no CDN: open weights served by Ollama locally.
- Footage never leaves the site; designed to run with Wi-Fi off.
- One laptop per few cameras; scale out with laptops or a GPU box.
- Operator fit: acknowledge on the card; false alarms per camera-hour is the metric.
- Every number is reproducible: committed benchmark files, commands in REPORT.md §10.

Speaker notes: Nothing in this stack phones home: the detector, the vision model, the database and the chat are files on this disk, and the models are open weights. That is the on-prem rule a security site lives by, and it is also why our numbers are honest: each one is a row in a committed benchmark file that anyone can regenerate with the commands in REPORT.md. The Wi-Fi-off run on the demo machine is still on the pending list, so we say designed for it, not measured.

Source: REPORT.md §8 (Wi-Fi-off run pending), §10 (reproduce commands). No measurements on this slide.

## Slide 7 - Model-independent by design

- The VLM and the chat model are one name in config.yaml.
- Needed from the server: Ollama chat API with streaming, JSON format, log-probabilities.
- Log-probabilities give the confidence bar; streaming gives the early alert.
- Qwen3.5-4B today; another open-weight VLM is a config change, not code.
- Gates, arbiter, events and dashboard never see the model name.

Speaker notes: The pipeline talks to one thin client that needs only a local chat endpoint with streaming, JSON-formatted output and token log-probabilities; that is how the probability bar and the early alert work. Change the model name in config.yaml and the gates, the arbiter, the event store and the dashboard carry on unchanged. The same name serves the chat, so one model is warmed and one model stays resident on the GPU.

Source: REPORT.md §1 (qwen3.5:4b-mlx via Ollama, config.yaml); SPEC.md §5 (model adapter: swapping model or backend is a config change). No measurements.

## Slide 8 - Why Qwen3.5 for Round 1; the Gemma A/B is planned, not done

- Shortlist (D9): Qwen3.5 2B/4B, LFM2.5-VL, Gemma 4.
- Round-1 pick (D22): Qwen3.5-4B, no full bake-off, to save time and disk.
- Gemma 4 and LFM2.5-VL were dropped untested: no Gemma number exists anywhere.
- P0 latency test: Qwen3.5 variants only (4B-MLX, 2B); model-only, no Gemma run.
- 4B over 2B: 4/7 vs 5/7 right, alerts p50 1207 vs 1492 ms; deferred.
- Gemma 4 A/B on the same clips planned (P6); swap = config change.

| Model only, P0, M4 (seconds) | Tile | Time to category p50 / p95 | Full call p50 / p95 |
|---|---|---|---|
| qwen3.5:4b-mlx | 160 | 1.603 / 2.190 | 3.539 / 4.357 |
| qwen3.5:4b-mlx | 224 | 1.740 / 2.004 | 3.679 / 4.085 |
| qwen3.5:2b | 160 | 1.229 / 1.797 | 2.305 / 3.594 |
| qwen3.5:2b | 224 | 1.347 / 1.455 | 2.437 / 2.612 |
| Gemma 4 (any size) | - | not measured | not measured |

Speaker notes: The brief lists Gemma and we had Gemma 4 on the shortlist; we picked Qwen3.5-4B for Round 1 without a full bake-off because a second model family cost time and disk we did not have, so there is no Gemma number in our files and we will not invent one. The only model comparison we ran is Qwen3.5 4B against 2B: on an early seven-clip run the 2B was one clip better but alerted slower, and with a single normal clip in that set the decision was deferred; the 4B is what runs today. The Gemma A/B on the same clips is planned, and because the model is one line in config.yaml it is a benchmark run, not a rewrite.

Source: numbers from REPORT.md §5c (model-only P0 table; it carries the qwen3.5:4b-mlx and qwen3.5:2b rows) and §4a (ab_model: 4/7 vs 5/7 right, trigger -> alert p50 1207 vs 1492 ms). Model names and reasons: DECISIONS.md D9, D22 (names only; no number taken from them). Plan: PLAN.md P6.

## Slide 9 - Honest limits

- 11 dev clips, fights and normal only: no fall, fire, crowd or tailgating clips.
- 6 public fight clips have no onset label; onset-to-alert exists for 1 clip.
- Normal footage 121.9 s, not the >= 30 min a false-alarm rate needs.
- Thresholds tuned on these dev clips; judged on a held-out split, never re-tuned.
- GPU duty target missed on 3 busy cameras: 91-99.5 % vs <= 60 %.
- Every number is from the M4; the M5, the judging machine, is unmeasured.

Speaker notes: We would rather you hear the limits from us: the clip set is small and covers fights and normal scenes only, so macro F1 over all 8 labels cannot be computed yet; the 0.641 in the report is over the 3 labels present. One fight clip got the wrong category, and the one onset-labelled clip missed the latency target by 216 ms on a single sample. Thresholds were tuned on these dev clips, so today's numbers are dev numbers; the held-out split, the longer normal footage and every M5 measurement are on the pending list, and until GPU duty is fixed the demo plays one clip at a time.

Source: REPORT.md §3 (11 clips, 6 without onset, 121.9 s, >= 30 min, hold-out note), §2 (8 labels), §4 (v026, macro F1 0.641 over 3 labels), §5b (n = 1, 216 ms), §5e (3 busy cameras 91-99.5 %, target <= 60 %), §1 / §8 / §9 (M5 pending).

## Slide 10 - Roadmap: the next numbers

- Accuracy: labelled test split with negatives; re-look; a classifier only if needed.
- Onset labels for the 6 public fight clips, then onset-to-alert p50 / p95.
- False alarms per camera-hour on >= 30 min of normal and look-alike footage.
- RTSP cameras; ESP32 guard console: hardware stopwatch, SOS, acknowledge / escalate.
- Shift-handover digests; watts per camera from powermetrics.
- Gemma 4 A/B on the same clips; M5 re-run, heat run, cold start.

Speaker notes: The next numbers are the ones a buyer asks for: accuracy on clips we never tuned on, including negatives, and false alarms per camera-hour on real idle footage. On the operator side we add RTSP cameras, a small hardware console for the guard with a stopwatch, an SOS button and acknowledge-or-escalate, and shift-handover digests. Watts per camera closes the on-prem argument: the running cost of a camera becomes a number, not a cloud bill.

Source: REPORT.md §9 (pending list: onset labels for the 6 public fight clips, test split, >= 30 min footage, watts per camera, M5 runs). Gemma A/B: PLAN.md P6. Shift-handover digests: SPEC.md §2. ESP32 is a part name, not a measurement.

---

Timing (minutes): S1 0.5 · S2 0.75 · S3 0.75 · S4 0.5 · S5 1.0 · S6 0.5 · S7 0.5 · S8 0.75 · S9 0.75 · S10 0.5 = 6.5, then straight into Act 1 of docs/DEMO_SCRIPT.md.

Who speaks: Shivansh (captain, model): S1, S2, S7, S8, S10 · Aryan (system, M5): S3, S6 · Abhinav (cameras): S4 · Riddhi (data, chat): S5, S9. Q&A: each answers their own area (crib in docs/DEMO_SCRIPT.md).
