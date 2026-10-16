# HackHive - final pitch deck (Honeywell PS3)

Sat 17 Oct 2026. A 6-7 minute talk by the team, then the live demo (docs/DEMO_SCRIPT.md). Plain markdown, one `## Slide` per slide.

Rules for this deck:
- Every number on a slide appears in REPORT.md and carries its section. Nothing is quoted from a plan, a decision log or memory.
- Every REPORT.md number was measured on the dev machine M4 (Apple M4, 16 GB); nothing has been re-measured on the demo machine M5 yet (REPORT.md header, §1).
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

- YOLO26n + ByteTrack at 10 fps per camera, on CPU: the always-on gate.
- Rules on person tracks (contact + speed, a fast drop, a body wider than tall) ask the model at once.
- A regular look every 3 s covers what no rule sees: fire, crowds, vandalism, theft.
- Qwen3.5-4B via Ollama sees one 2x2 letterboxed mosaic: 4 frames spanning 2 s.
- 8 labels, a probability for each from the token log-probabilities; events in SQLite.
- The chat answers only with cited stored events.

Speaker notes: A vision-language model on every frame does not fit on a laptop, so an always-on detector and a few rules on person tracks decide when the model should look right now. Fire, crowds, vandalism and theft have no people-rule, so a regular look every few seconds covers them. The model sees four recent frames as one letterboxed mosaic and streams back structured JSON; the probability of each of the 8 labels comes from its token log-probabilities, and event rules turn those into alerts. Every alert is stored, and the chat is only allowed to talk about stored events.

Source: REPORT.md §1 (YOLO26n + ByteTrack, 10 fps, baseline every 3 s, Qwen3.5-4B as qwen3.5:4b-mlx via Ollama, 2x2 letterboxed mosaic, 8 labels, log-probabilities). CPU and the rules are design facts (SPEC.md §5), not numbers.

## Slide 3 - Architecture: one pipeline, every stage timed

- Capture (latest frame only) -> YOLO + ByteTrack -> rules + change-gated regular looks.
- One arbiter: priority queue, rule-triggered calls first, stale requests dropped.
- Streaming VLM -> detector cross-check -> event rules -> alert.
- Events: SQLite + FTS5 + key frames -> FastAPI -> SSE -> Next.js dashboard.
- Chat: the model reads the question -> SQL/FTS5 finds -> the model answers, every sentence cited.
- One coordinate system end to end; every stage timed in the Pipeline view.

Speaker notes: Each camera keeps only its latest frame, runs the detector on the CPU and feeds person tracks to the rules; a regular look, skipped while nothing and nobody moves, covers what the rules cannot see. One arbiter owns the single GPU: rule-triggered calls go first and stale requests are dropped, so a fight on one camera never waits behind a routine look at an empty corridor. The detector cross-checks the model (no people seen, no fight), event rules decide when probabilities become an alert, and the dashboard shows every stage's timing.

Source: no numbers on this slide (architecture as in SPEC.md §5).

## Slide 4 - How we set the parameters: record once, replay offline

- One real pass records every model call: probabilities, detector evidence, the hint, the frames.
- Replay re-runs the event rules on the recordings with any setting: bit-exact, no GPU.
- Each threshold swept on the 16 dev clips only, by a rule fixed in advance; then one real pass confirms.
- Finding: the thresholds sat on a plateau. What mattered was what the model was told.
- The hint "(possible fight)" made the model agree; naming the look-alikes fixed it: dev gate calls right 4 -> 10 of 17.
- Result on the test clips: false alarms 6 -> 3. Cost: a brief shove now alerts on the second look.

Speaker notes: We were asked how we determine our parameters, so we built a method instead of guessing. One real pass through the pipeline records every model call; after that, any threshold can be replayed offline in seconds, exactly as the live run would have scored it, and swept on the tuning clips only. The sweep was flat, so the thresholds stayed. What moved the numbers was the hint the rule sends with its call: "possible fight" made the model call a running crowd or someone helping a fallen person a fight. Naming the look-alikes and leaving the call to the frames more than doubled the right gate calls on the tuning clips and halved the false alarms on the test clips. The honest cost is latency on a brief shove, which now waits for a second look.

Source: REPORT.md §4 (method, plateau, bit-exact replay, 16 dev clips), §5d (4 -> 10 of 17 dev gate calls), §5a (test false alarms 6 -> 3), §6a (brief shove on the second look).

## Slide 5 - Live demo plan: three acts, and what to watch

- Act 1, clips: the v011.avi fight alerts; sample_bus.mp4 ends with "No incidents".
- The floor_sit.mp4 look-alike wakes the model, which says normal; fire_bucket.mp4 is caught with no rule behind it.
- Your own video: upload any common format; it runs with nothing tuned on it.
- Act 2, live (webcam + iPhone): a staged shove alerts; a floor-sit does not.
- Act 3, chat: "Show all tailgating events from camera 2 today", then two more.
- Watch for: the probability bar, trigger -> alert on the card, the hint and mosaic in Pipeline, the raw JSON.

Speaker notes: Three acts follow the slides: recorded clips, two live cameras, then the chat; the script and every fallback are in docs/DEMO_SCRIPT.md. If you brought a video, we upload it in Act 1: nothing was tuned on it, and the verdict shows every alert with its time in the clip. Act 3 asks the brief's own example, "Show all tailgating events from camera 2 today", then "What incidents happened in the last 10 minutes?" and a summary of the lobby. We quote no numbers on stage: the card shows trigger -> alert, the verdict puts the labelled onset next to the alert time, and REPORT.md has the rest.

Source: clip names as in REPORT.md §3; the brief's question as quoted in REPORT.md §9. Act order and fallbacks: docs/DEMO_SCRIPT.md.

## Slide 6 - Measured: M4, 31 clips, one at a time

- Every figure is a row in a committed bench/results/ file, via REPORT.md.
- Tuned on 16 dev clips, scored on 15 test clips; we read the first test run's errors, so the test score is a check, not a clean held-out number.

| Measure | Result | Target (SPEC §4) | REPORT.md |
|---|---|---|---|
| Clips right, test | 4 of 15 (3 before D86) | - | §5a |
| Clips right, dev (tuned on) | 9 of 16 | - | §5b |
| Right by category, test | fire 2/2, crowd 1/1, theft 1/1; falls 0/5, vandalism 0/4, fight 0/1, normal 0/1 | - | §5a |
| Incident recall / precision, test | 8 of 14 / 8 of 9 | >= 0.85 / >= 0.85 | §5a |
| False alarms on normal footage | test 3 in 4.5 camera-min (6 before D86); dev 2 in 3.1 | <= 1 per camera-hour, on >= 30 min | §5a, §5b |
| Macro F1, fixed 8 labels, test | 0.312 (0.250 before D86); not a valid final number | >= 0.75 | §5a |
| Onset -> alert, fights (laptop cool) | 1.4-5.2 s, p50 2.7 s, 6 of 7 read right | p95 <= 3.0 s: missed | §6a |
| Onset -> alert, fire / crowd / theft | 7.0-9.9 s | - | §6b |
| Trigger -> alert, fights (laptop cool) | p50 1386 ms (1190-1977) | - | §6a, §6c |
| Model time-to-alert, p50 per clip | 1236-1441 ms | p95 <= 2.0 s | §6a |
| YOLO per frame | 15.6-24.6 ms | <= 40 ms | §6a |
| GPU duty | 1 clip at a time 68-74 %; 3 busy cameras 91-99.6 % (before D86) | <= 60 % with 3 cameras: missed | §6d |
| Chat, seeded history | 45 of 48 right; 0 invented events; 0 uncited sentences | - | §9 |
| Chat model answers | p50 2610 ms, p95 6661 ms; 4 of 38 over 5 s | <= 5 s | §9 |
| Cold start, ./run_demo.sh | M4 10.2 s; M5 pending | < 2 min | §11 |

Speaker notes: Fire, the crowd crush and the theft were caught on clips we never tuned on; fights are fast on our tuning clips, with a median of 2.7 seconds from the first blow to the alert. The weak spots are falls and vandalism, and we show them rather than hide them: no fall was caught after its onset, and vandalism comes out as suspicious activity, still an alert, under the wrong label. False alarms halved with the method on the previous slide. Against the targets, the fight latency misses 3 seconds at p95 and three busy cameras overload one laptop's GPU, which is why the demo plays one clip at a time.

Source: REPORT.md §1, §3 (split, test seen during tuning), §5a, §5b, §6a-§6d, §9, §11. All measured on the M4 (REPORT.md header).

## Slide 7 - Why local, on-prem: built for a Honeywell site

- No cloud, no API keys, no CDN: open weights served by Ollama locally.
- Footage never leaves the site; designed to run with Wi-Fi off.
- One laptop per few cameras; scale out with laptops or a GPU box.
- Operator fit: acknowledge or mark a false alarm on the card; false alarms per camera-hour is the metric.
- Every number is reproducible: committed benchmark files and recordings, commands in REPORT.md §13.

Speaker notes: Nothing in this stack phones home: the detector, the vision model, the database and the chat are files on this disk, and the models are open weights. That is the on-prem rule a security site lives by, and it is also why our numbers are honest: each one is a row in a committed benchmark file that anyone can regenerate with the commands in REPORT.md. The Wi-Fi-off run on the demo machine is still on the pending list, so we say designed for it, not measured.

Source: REPORT.md §12 (Wi-Fi-off run pending), §13 (reproduce commands). No measurements on this slide.

## Slide 8 - Model-independent by design

- The VLM is one name in config.yaml; the chat model is another (by default the same one).
- Needed from the server: Ollama chat API with streaming, JSON format, log-probabilities.
- Log-probabilities give the confidence bar; streaming gives the early category.
- Qwen3.5-4B today; another open-weight VLM is a config change, not code.
- Rules, arbiter, events and dashboard never see the model name.

Speaker notes: The pipeline talks to one thin client that needs only a local chat endpoint with streaming, JSON-formatted output and token log-probabilities; that is how the probability bar and the early category work. Change the model name in config.yaml and the rules, the arbiter, the event store and the dashboard carry on unchanged. By default the chat uses the same model, so one model is warmed and stays resident on the GPU; the chat can also point at a different model.

Source: REPORT.md §1 (qwen3.5:4b-mlx via Ollama); SPEC.md §5 (model adapter) and §10 (`vlm.model`, `chat.model`). No measurements.

## Slide 9 - Why Qwen3.5; the Gemma A/B is planned, not done

- Shortlist (D9): Qwen3.5 2B/4B, LFM2.5-VL, Gemma 4.
- Pick (D22): Qwen3.5-4B, no full bake-off, to save time and disk.
- Gemma 4 and LFM2.5-VL were dropped untested: no Gemma number exists anywhere.
- P0 latency test: Qwen3.5 variants only (4B-MLX, 2B), model-only.
- 4B over 2B on an early 7-clip run: 4/7 vs 5/7 right, but alerts p50 1207 vs 1492 ms.
- A Gemma 4 A/B on the same clips is a config change plus one recorded pass.

| Model only, P0, M4 (seconds) | Tile | Category token p50 / p95 | Full call p50 / p95 |
|---|---|---|---|
| qwen3.5:4b-mlx | 160 | 1.603 / 2.190 | 3.539 / 4.357 |
| qwen3.5:4b-mlx | 224 | 1.740 / 2.004 | 3.679 / 4.085 |
| qwen3.5:2b | 160 | 1.229 / 1.797 | 2.305 / 3.594 |
| qwen3.5:2b | 224 | 1.347 / 1.455 | 2.437 / 2.612 |
| Gemma 4 (any size) | - | not measured | not measured |

Speaker notes: The brief lists Gemma and we had Gemma 4 on the shortlist; we picked Qwen3.5-4B without a full bake-off because a second model family cost time and disk we did not have, so there is no Gemma number in our files and we will not invent one. The only model comparison we ran is Qwen3.5 4B against 2B: on an early seven-clip run the 2B was one clip better but alerted slower, and with a single normal clip in that set the decision was deferred; the 4B is what runs today. With the record-and-replay method, a Gemma A/B is one recorded pass on the same clips.

Source: numbers from REPORT.md §11 (model-only P0 table; model A/B 4/7 vs 5/7, trigger -> alert p50 1207 vs 1492 ms). Model names and reasons: DECISIONS.md D9, D22 (names only; no number taken from them).

## Slide 10 - Honest limits

- Test 4 of 15: falls 0/5, vandalism 0/4 (filed as suspicious activity), a top-down bar fight missed.
- Falls: the clips open with a deliberate look-alike, and the detector loses a person lying down.
- We read the test clips' errors before choosing fixes: a check, not a clean held-out score.
- Fights miss the 3 s p95 target (max 5.2 s); brief shoves got slower with the hint fix.
- 4.5 camera-minutes of normal test footage, not the 30 a false-alarm rate needs; no tailgating clip.
- 3 busy cameras: GPU duty 91-99.6 % vs <= 60 %; every number is from the M4, not the M5.

Speaker notes: We would rather you hear the limits from us. Falls are our weakest category: the fall clips start with someone lying down on a mattress on purpose, the model calls that a fall seconds early, and when the real fall comes, the detector often cannot see a person lying on the floor, so a safety veto cut a real fall the model did see. Vandalism raises an alert, but under suspicious activity. We read the first test run's errors before choosing our fixes, so we report the test score as a check, not as a held-out estimate; a fresh clip set is the next held-out test. The hint fix halved false alarms but made a brief shove wait for a second look, so fights miss our 3-second target at the tail.

Source: REPORT.md §5a, §5e (falls, vandalism, the veto), §3 (test seen, 4.5 camera-min, no tailgating clip), §6a (max 5.2 s, target 3.0 s), §6d (91-99.6 %), header and §12 (M5 pending).

## Slide 11 - Roadmap: the next numbers

- A fresh held-out clip set, labelled before any run, scored once.
- Falls: a staged fall on the high camera; rethink the person_down veto for people lying down.
- The second look (D87, built, off): one A/B with the real model decides it.
- Vandalism: the model never answers property damage; new wording or a small classifier.
- False alarms per camera-hour on >= 30 min of normal footage; 3-camera duty and latency on the M5.
- Gemma 4 A/B; ESP32 guard console (stopwatch, SOS, acknowledge / escalate); watts per camera.

Speaker notes: The next numbers are the ones a buyer asks for: accuracy on clips nobody has seen, false alarms per camera-hour on real idle footage, and falls, which need a detector that sees people lying down. The second look for an unverified person down is already built and switched off; one recorded A/B pass with the real model decides whether it stays. On the operator side: a small hardware console for the guard and watts per camera, which turns the running cost of a camera into a number instead of a cloud bill.

Source: REPORT.md §12 (pending list), §5c (property_damage never answered), §5e (the veto), §7 (the second look, off). ESP32 is a part name, not a measurement.

---

Timing (minutes): S1 0.5 · S2 0.75 · S3 0.5 · S4 0.75 · S5 0.5 · S6 1.0 · S7 0.5 · S8 0.5 · S9 0.5 · S10 0.75 · S11 0.5 = 6.75, then straight into Act 1 of docs/DEMO_SCRIPT.md.

Who speaks: Shivansh (captain, model): S1, S2, S4, S8, S9, S11 · Aryan (system, M5): S3, S7 · Abhinav (cameras): S5 · Riddhi (data, chat): S6, S10. Q&A: each answers their own area (crib in docs/DEMO_SCRIPT.md).
