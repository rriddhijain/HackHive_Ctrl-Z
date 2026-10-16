# HackHive - Round-1 report: accuracy and latency (preliminary)

Fri 16 Oct 2026, 05:45 IST. SPEC v1.15 (the headline run is tagged `v1.14`: its gate rules are the v1.14/D72 ones, which v1.15 did not change).
Machine: every number below was measured on the dev machine M4 (Apple M4, 16 GB). Judging is on the demo machine M5 (Apple M5). Nothing has been re-measured on the M5 yet.
Preliminary: dev clips only, one camera at a time, no held-out test split. Every number comes from a file under `bench/results/` (named under each block) or is quoted as a setting (`config.yaml`), a target (SPEC §4) or a label (`bench/labels.csv`).

> **Update, branch `fix/benchmark-metrics-v026` (16 Oct, evening).** Section 11 adds: the independently re-verified
> 0.641 and what it is (an observed-label dev diagnostic), the fixed 8-label metric status (not a final metric: no
> test split, 6 of 8 classes without clips), a detector-level diagnosis of v026 on the real clip, and the proposed
> person_down second look, alert-first with a linked, visible correction (D83). **No vision-model benchmark was re-run on this branch**: every new number in section 11
> is detector-only (CPU, no model) or re-computed from the committed result files.

## 1. In one minute

- What it is: a YOLO26n person detector at 10 fps per camera gates a local Qwen3.5-4B vision model (`qwen3.5:4b-mlx` via Ollama, `config.yaml`). The model sees a 2x2 letterboxed mosaic of 4 frames spanning 2 s (288x160 tiles). Verdicts become events in SQLite; the chat answers only from those events. Fully local, no cloud. Each 2 s window gets one of 8 labels: fighting, person_down (a fall), fire_smoke, crowd_incident, tailgating, property_damage, suspicious_activity or normal; the dev clips cover fighting and normal only.
- Accuracy (11 clips, each played once, alone): 10 of 11 clips right. All 7 incident clips raised an incident (recall 1.00); none of the 4 normal/look-alike clips raised an alert (precision 1.00, 0 false alarms). The one error: v026, a fight read as `person_down`. Macro F1 0.641 over the 3 labels present; not comparable with the 8-label target. The fight-gate thresholds were tuned on these same 11 clips (section 3), so 10 of 11 is a training-set result; the held-out test split (P8) does not exist yet. The 4 normal clips total 2 camera-minutes, so "0 false alarms" is a count over 2 minutes, not a rate (SPEC §12 needs >= 30 min).
- Latency (same run): trigger -> alert p50 1268 ms, max 1332 ms over 7 alerts (with n = 7 the p95 is the max). Onset-to-alert, the number a judge times, exists for one clip only, measured twice: 3216 ms (pipeline run, ab_p5_dev.csv) and 3141 ms (browser run, p5_cold_start.json) against a target of p95 <= 3000 ms; both over (by 216 and 141 ms), two measurements of one clip, so no p95. Clip-start -> alert for the other fights: 2.9 s to 4.4 s (an upper bound).
- Chat: 45 of 48 questions right on a seeded history, 0 invented events, 0 uncited sentences; the model writes the answers (p50 2.7 s, p95 5.9 s, 3 of 38 over 5 s).
- Not measured yet: anything on the M5 (cold start, latency, 10-min heat run); onset labels for the 6 public fight clips; person_down (fall), fire_smoke, crowd_incident and tailgating clips; >= 30 min of normal footage (false alarms per camera-hour); watts per camera. Store -> card was measured on the M4 (p5_cold_start.json, 05:48 IST): p50 13.0 ms, p95 20.2 ms, n = 2; M5 pending.
- Missed target: GPU duty with 3 busy cameras 91-99.6 % against <= 60 % (section 5e); that is why the demo plays one clip at a time.
- Honesty rule (SPEC NFR-7): no number here comes from a plan, a decision log or an estimate.

## 2. Definitions used (SPEC §12)

| Term | Meaning | Note |
|---|---|---|
| Onset-to-alert | alert SSE sent - incident onset (`onset_s` in `bench/labels.csv` on the replay clock; live: a 240 fps video showing the fall and the toast) | what a judge times; includes gate delay, queue wait and baseline wait |
| Trigger -> alert | alert sent - gate trigger time (or baseline request time) | shown on each alert card |
| Model time-to-alert | t_category - t_capture: newest mosaic frame -> category token known | excludes detection and queue; never quoted alone |
| Store -> card | alert stored in the DB -> card painted in the browser | browser-measured via `POST /api/ui/latency` (SPEC v1.9 note) |
| GPU duty | share of wall time a model call is running, over a 60 s window | target <= 60 % average with 3 cameras (NFR-4) |
| Clip prediction | highest-confidence non-`normal` event in the clip, else `normal` | used for every accuracy run |
| Macro F1 | over all 8 labels (7 incident categories + `normal`) on the held-out test set | target >= 0.75 (NFR-2) |
| Incident-vs-normal recall / precision | the same clip predictions collapsed to incident vs `normal` | targets >= 0.85 and >= 0.85 |
| False alarms per camera-hour | events opened on >= 30 min of footage labelled normal (incl. look-alikes) / camera-hours | target <= 1 |
| Labels | one of 8 per 2 s window (SPEC §4/§12: 7 incident categories + `normal`): fighting, person_down (a fall), fire_smoke, crowd_incident, tailgating, property_damage, suspicious_activity, normal (names as in the top-3 column of ab_p5_dev.csv) | the dev clips cover fighting and normal only |
| Gate | a rule on the YOLO person boxes (for fighting: box speed, box-height ratio and contact time, `gate.fight_*` in `config.yaml`; for person_down: a horizontal box or a fast drop, `gate.down_ratio` / `gate.drop_frac`) that decides when a camera's last 2 s of frames (`vlm.mosaic_span_s`) are sent to the vision model; "gate fired" = the rule held and a model call was made | the cheap check in front of the expensive model |
| Baseline call | a model call made every 3 s per camera whether or not the gate fired (`config.yaml vlm.baseline_interval_s`) | how v026 and w001_masked were caught |
| Trigger | the gate fire or the baseline request that led to the alert | start of the trigger -> alert clock |
| SSE | the server's push of the alert to the browser | end of the onset-to-alert clock |
| VLM | the Qwen3.5 vision-language model (`config.yaml vlm.model`) | the only model that names a category |
| Veto | the detector's person count contradicting the model's category, which cuts that category's probability; logged per category (SPEC §12 veto log) | a veto on a real incident is a lost alert; on a normal clip, a false alarm removed |

Source: SPEC.md §12 (definitions), §4 (targets), v1.9 header note (store -> card); config.yaml (gate, vlm keys); bench/results/ab_p5_dev.csv (label names).

## 3. The clip set and what it cannot measure

| Clip | Label | Source | Length (s) | onset_s |
|---|---|---|---|---|
| v001.avi | fighting | public fight clip | 6.4 | - |
| v003.avi | fighting | public fight clip | 3.0 | - |
| v006.avi | fighting | public fight clip | 5.8 | - |
| v011.avi | fighting | public fight clip | 8.7 | - |
| v026.avi | fighting | public fight clip | 9.7 | - |
| w001_masked.avi | fighting | public fight clip | 5.1 | - |
| p3c_shove_sit_hug.mp4 | fighting | webcam, staged shove; a floor-sit and a hug later in the same take as look-alikes | 29.9 | 5.6 |
| sample_bus.mp4 | normal | street scene with a bus (model summary text) | 12.0 | - |
| idle_60s.mp4 | normal | webcam, idle scene | 60.0 | - |
| floor_sit.mp4 | normal | webcam look-alike (sitting on the floor) | 19.9 | - |
| desk_closeup.mp4 | normal (not in labels.csv; label from ab_p5_dev.csv and gate_check_p5.txt) | webcam look-alike (desk close-up) | 30.0 | - |

Source: bench/labels.csv (clip, label, onset_s for 10 clips; desk_closeup.mp4 has no row there); bench/results/gate_check_p5.txt (length; desk_closeup label); bench/results/ab_p5_dev.csv (summary column for the clip content; desk_closeup label).

What this set cannot measure:
- desk_closeup.mp4 was removed from the dev set and the demo playlist after this run (captain, 16 Oct 05:56 IST). The results files keep its row as measured, so the counts in this report (11 clips, 10 of 11 right, 4 normal/look-alike clips) include it; without it the set is 10 clips, 9 of 10 right, 0 false alarms on 3 normal/look-alike clips.
- Onset-to-alert exists for 1 clip. The 6 public fight clips have no `onset_s` yet; for them only clip-start -> alert is known, an upper bound (the incident starts after the clip does).
- Only fighting vs normal is tested. There are no person_down (fall), fire_smoke, crowd_incident, tailgating, property_damage or suspicious_activity clips, so macro F1 over the 8 labels is not computable; the 0.641 below is over the 3 labels present.
- Normal footage totals 121.9 s (2.0 camera-min), not the >= 30 min SPEC §12 needs for false alarms per camera-hour. All footage together is 190.5 s.
- No labelled test split exists yet; the 10 clips in bench/labels.csv are all `dev`; desk_closeup.mp4 has no labels.csv row and so no split.
- Hold-out note: the fight-gate thresholds (`fight_speed` 0.6, `fight_min_height_ratio` 0.5, `fight_contact_s` 0.5 in `config.yaml`) were tuned on these dev clips, so the dev numbers are optimistic. They will be judged on a held-out test split (P8) and never re-tuned on it.

## 4. Accuracy (headline run: ab_p5_dev)

Run: v1.14 gates, `qwen3.5:4b-mlx`, all 11 clips, each alone through the real pipeline, played once, M4, 16 Oct 05:35 IST.

| Clip | Label | Predicted | Conf. | Top-3 | Right |
|---|---|---|---|---|---|
| p3c_shove_sit_hug.mp4 | fighting | fighting | 1.000 | fighting 1.00, person_down 0.01, normal 0.01 | yes |
| v001.avi | fighting | fighting | 1.000 | fighting 1.00, crowd_incident 0.01, suspicious_activity 0.00 | yes |
| v003.avi | fighting | fighting | 0.845 | fighting 0.85, person_down 0.21, suspicious_activity 0.02 | yes |
| v006.avi | fighting | fighting | 0.964 | fighting 0.96, suspicious_activity 0.06, property_damage 0.04 | yes |
| v011.avi | fighting | fighting | 1.000 | fighting 1.00, suspicious_activity 0.00, fire_smoke 0.00 | yes |
| v026.avi | fighting | person_down | 0.913 | person_down 0.91, fire_smoke 0.02, normal 0.02 | no |
| w001_masked.avi | fighting | fighting | 0.840 | fighting 0.84, person_down 0.13, property_damage 0.02 | yes |
| desk_closeup.mp4 | normal | normal | 1.000 | normal 1.00, suspicious_activity 0.00, fire_smoke 0.00 | yes |
| floor_sit.mp4 | normal | normal | 0.998 | normal 1.00, suspicious_activity 0.00, fire_smoke 0.00 | yes |
| idle_60s.mp4 | normal | normal | 0.996 | normal 1.00, suspicious_activity 0.00, person_down 0.00 | yes |
| sample_bus.mp4 | normal | normal | 0.991 | normal 0.99, suspicious_activity 0.01, tailgating 0.00 | yes |

Source: bench/results/ab_p5_dev.csv.

- Right: 10 of 11. Incident-vs-normal recall 1.00 (7 of 7 incident clips raised an incident), precision 1.00 (0 normal clips raised one). False alarms on the 4 normal/look-alike clips: 0. Vetoes recorded in the `vetoes` column of ab_p5_dev.csv: none on any clip.
- Confusion: fighting -> person_down on v026. The model saw "A person is lying on the floor in a hallway while another person stands nearby." The gate never fired on v026 (gate_check_p5.txt: KNOWN MISS, the detector never sees both fighters), so the card came from a baseline call. An incident card was raised, with the wrong category.
- Look-alikes: the gate fired once each on desk_closeup (person_down @15.3 s), floor_sit (fighting @16.5 s) and idle_60s (fighting @31.1 s); the model answered `normal` (>= 0.996) each time, so no alert. In p3c the gate also fired at 23.8 s, during the look-alike part of the take; a second model call ran and no second alert was raised (alerts = 1).
- Macro F1 0.641 over the labels present (fighting, normal, person_down). From the table: fighting precision 1.00, recall 6/7 = 0.857, F1 0.923; normal F1 1.00; person_down has 0 true clips and 1 prediction, F1 0. Mean of the three = 0.641. This is not the 8-label NFR-2 number.

Source: bench/results/ab_p5_dev_summary.json; ab_p5_dev.csv (summary, gate_fired, alerts, vetoes columns); gate_check_p5.txt.

### 4a. History: older gates (before D72), 7 clips (6 fights + sample_bus), 16 Oct 03:05-03:20 IST

| Run | Variant | Right | Incident recall / precision | Trigger -> alert p50 / p95 (ms) | GPU duty (% of wall time; target <= 60 % with 3 cameras) | Errors |
|---|---|---|---|---|---|---|
| ab_model | qwen3.5:4b-mlx | 4 / 7 | 0.667 / 1.00 | 1207 / 1261 | 79 % | v001, v003 -> normal; v026 -> person_down |
| ab_model | qwen3.5:2b | 5 / 7 | 0.667 / 1.00 | 1492 / 1914 | 85 % | v026, w001_masked -> normal |
| ab_tiles | 2x2 mosaic | 4 / 7 | 0.833 / 1.00 | 3163 / 4998 | 87 % | v003, v026 -> person_down; w001_masked -> normal |
| ab_tiles | person-crop tile | 4 / 7 | 0.667 / 1.00 | 2605 / 3221 | 89 % | v003, w001_masked -> normal; v026 -> person_down |
| ab_tiles | native video (4 separate frames) | 5 / 7 | 0.833 / 1.00 | 5886 / 7514 | 97 % | v026 -> person_down; w001_masked -> normal |

Source: bench/results/ab_model_summary.json, ab_tiles_summary.json.

Decisions, not measurements. Current default: the 4B. On this pre-D72 run the 2B got one more clip right (5/7 vs 4/7) but both have the same incident recall (0.667: each read 2 fights as normal; the 4B's third error was a fight read as `person_down`, still an incident); the 4B alerted 285 ms faster at p50 (1207 vs 1492 ms). The final 4B-vs-2B choice is deferred to the P6 A/B because this run had one normal clip, so neither model has been judged on false alarms. These rows are not comparable with section 4: the gates changed, the model did not. Veto log: veto counts are logged per run (`vetoes_logged`, `vetoes_p_ge_0.3` in ab_run_*_totals.json and p2a_*.json: 0-2 vetoes with p >= 0.3 per run); no review record exists under bench/results. Mosaic kept over native video: native video was right on one more clip but alerted 1.9x slower at p50 (5886 vs 3163 ms) and ran the GPU at 97 %. The same 4B model with the v1.14 gates got 6 of these 7 clips right (section 4 table); the gates changed between the two runs, not the model.

## 5. Latency

Targets (SPEC §4 NFR-1): onset-to-alert p95 <= 3.0 s for gate-triggered categories; model time-to-alert p95 <= 2.0 s; VLM full call p50 <= 3.7 s, p95 <= 4.1 s; YOLO <= 40 ms/frame; all under 3-camera demo load. The headline run is one clip at a time, not 3-camera load, and has 7 alerts, below the >= 50 events SPEC §12 asks for. The VLM-call targets (p50 3.7 s, p95 4.1 s) and the model time-to-alert target (p95 2.0 s) are this project's own 15 Oct P0 measurement (4b-mlx, tile 224) rounded, kept as a regression guard; they are not from the brief. The target a judge can time is onset-to-alert p95 <= 3.0 s.

### 5a. Trigger -> alert and clip-start -> alert (ab_p5_dev, ms)

| Clip | Gate fired (clip s) | Trigger -> alert | Clip-start -> alert | Onset-to-alert |
|---|---|---|---|---|
| p3c_shove_sit_hug.mp4 | fighting @7.5 | 1268 | 8816 | 3216 (onset 5.6 s) |
| v001.avi | fighting @1.9 | 1332 | 3229 | no onset label |
| v003.avi | fighting @1.7 | 1212 | 2901 | no onset label |
| v006.avi | fighting @2.9 | 1298 | 4186 | no onset label |
| v011.avi | fighting @2.1 | 1295 | 3378 | no onset label |
| v026.avi | none (baseline call) | 1239 | 4426 | no onset label |
| w001_masked.avi | none (baseline call) | 1142 | 4227 | no onset label |
| All 7 alerts | | median 1268, max 1332 | median 4186, max 8816 | one clip: 3216 (3141 in a second run, p5_cold_start.json) |

The gate-fire times in this table are from the real-time pipeline run and are the ones the alerts were timed from. The offline gate check (sections 6a/6b) replays the same clips and reports different first-fire times on every clip (v011: 2.1 s here vs 5.6 s there; w001_masked: no fire here vs 1.6 s there); the cause has not been established and the two must not be read as the same measurement.

Source: bench/results/ab_p5_dev.csv, ab_p5_dev_summary.json. For v026 and w001_masked the trigger is the baseline request (SPEC §12). The summary file pools only the 6 clips whose prediction was right (v026 excluded) and takes a nearest-rank percentile: clip-start p50 3378 ms is the 3rd of those 6 sorted values, trigger -> alert p50/p95 1268/1332 ms. This table uses all 7 alerts.

### 5b. Onset-to-alert (what a judge times)

One clip has an onset label. p3c_shove_sit_hug: onset 5.6 s (chest to chest), gate fired at 7.5 s (1.9 s after onset), alert 1268 ms after the trigger, so the alert came at 8.816 s on the clip clock = 3216 ms after onset. Target: p95 <= 3000 ms for gated categories. Result: missed by 216 ms. A second run of the same clip (p5_cold_start.json: browser on the dashboard, M4, 05:48 IST) measured 3141 ms, missed by 141 ms. Two measurements of one clip and one category, so no p95 can be given. Most of the delay is the gate (1.9 s), not the trigger -> alert path (1.3 s). For the 6 public fight clips, clip-start -> alert (2901-4426 ms) is the upper bound until onsets are labelled.

Source: bench/results/ab_p5_dev.csv; bench/results/p5_cold_start.json (onset_to_alert_ms); bench/labels.csv (onset_s); SPEC.md §4.

### 5c. Model only, not alert latency (P0, 15 Oct 21:52-21:54 IST, seconds)

These exclude the gate, the queue and capture (SPEC §12). Never quote them as "latency". t_cat = time to the category token (model time-to-alert); total = full call. Contention = one chat call + 2 camera calls queued on the one GPU, single run, category time of the chat, the 1st and the 2nd camera.

| Model | Tile | t_cat p50 / p95 (target p95 <= 2.0) | total p50 / p95 (target 3.7 / 4.1) | Contention: chat / 1st cam / 2nd cam t_cat |
|---|---|---|---|---|
| qwen3.5:4b-mlx | 160 | 1.603 / 2.190 | 3.539 / 4.357 | 2.307 / 3.700 / 6.914 |
| qwen3.5:4b-mlx | 224 | 1.740 / 2.004 | 3.679 / 4.085 | 2.288 / 4.177 / 7.949 |
| qwen3.5:2b | 160 | 1.229 / 1.797 | 2.305 / 3.594 | 1.567 / 2.866 / 5.438 |
| qwen3.5:2b | 224 | 1.347 / 1.455 | 2.437 / 2.612 | 1.554 / 3.118 / 5.679 |

Against these targets the 4b-mlx tile-160 row misses both p95s (4.357 s and 2.190 s) and the tile-224 row misses t_cat p95 by 4 ms; the 288x160 tiles the pipeline uses today have not been measured in this form.

Source: bench/results/latency_p0_tile160.json, latency_p0_tile224.json. The SPEC §4 targets (VLM 3.7 / 4.1 s, model time-to-alert p95 2.0 s) were set from the 4b-mlx tile-224 row. The pipeline now uses 288x160 tiles (`config.yaml vlm.tile`), not re-measured in this P0 form. An earlier P0 file (latency_p0.json, 15 Oct 21:51 IST, longer output format, tile size not recorded in the file) had 4b-mlx t_cat 3.102 / 3.340 s, total 4.603 / 5.195 s.
NFR-1a (1st camera <= 2.5 s, 2nd <= 4.5 s p95, with a chat question) has not been stress-tested; the single-run model-only contention above is already above both numbers for both models.

### 5d. Store -> card (SSE -> card paint, browser-measured)

Measured in Chrome on the M4 with the dashboard open while two clips played once (v011, p3c_shove_sit_hug): p50 13.0 ms, p95 20.2 ms, n = 2 alerts (SPEC v1.9 budget <= 100 ms). Few samples: the number is re-measured by the browser on every alert and shown on the metrics strip.

Source: bench/results/p5_cold_start.json (store_to_card_ms).

### 5e. GPU duty (share of wall time a model call runs, 60 s window)

| Load | Run | GPU duty (% of wall time; target <= 60 % with 3 cameras) | Met? | Model time-to-alert p50 (ms) | Alerts raised | Trigger -> alert (ms) | Notes |
|---|---|---|---|---|---|---|---|
| 1 clip at a time, 11 clips (3-60 s each) | ab_p5_dev | 75 % mean | - (not a 3-camera load) | - | 7 | see 5a | |
| 1 idle camera (sample_bus looping, 60 s), before load control | ab_run_bus60_before | 53 % | yes | 1262 | 0 | - | |
| 1 idle camera, after load control | ab_run_bus60_after | 56 % | yes | 1275 | 0 | - | |
| 3 static cameras, 60 s | p2a_duty_static_x3 | 39 % | yes | 1372 | 0 | - | 45 baselines skipped |
| 3 cameras: fight + normal + static, before | ab_run_duty_mix_before | 99.6 % | no | 1408 | 2 | fighting 4273; person_down 17202 | |
| 3 cameras: fight + normal + static, after back-off (baseline calls skipped while the GPU is busy) | ab_run_duty_mix_after | 94.1 % | no | 2594 | 2 | fighting 1275; person_down 16285 | |
| 3 fight cameras, before | ab_run_duty_fights3_before | 99.5 % | no | 15514 | 3 | 7948; 15428; 12121 | |
| 3 fight cameras, after back-off | ab_run_duty_fights3_after | 99.5 % | no | 14520 | 2 | 6397; 7291 | |
| 3 fight cameras, stop generating once the category word is out | ab_run_duty_fights3_stopcat | 91.0 % | no | 4376 | 6 | 590; 4779; 6041; 7793; 4234; 4318 | |
| 7 cameras at once (first dev run, 29.7 s) | p2a_dev | 96.2 % | no | 11693 | 1 | - | 1 of 6 fight clips caught |

Source: bench/results/ab_p5_dev_summary.json; ab_run_bus60_*_totals.json; ab_run_duty_mix_*_totals.json; ab_run_duty_fights3_*_totals.json; p2a_duty_static_x3.json; p2a_dev.json.

Target: average GPU duty <= 60 % with 3 cameras (NFR-4). Result: 1 idle camera 53-56 %; 3 static cameras 39 %; any 3 cameras with people moving 91-99.6 %: missed. Under that load model time-to-alert p50 is 1.4-15.5 s against the p95 <= 2.0 s target: missed in 4 of 5 runs. The one-clip-at-a-time headline run itself averaged 75 % on short clips. Consequence for the demo: Clips mode plays one clip at a time; Live mode warns when more than a few live sources are added.

## 6. Gates

### 6a. Plain yolo26n vs yolo26n-pose for the fight gate (ab_gate.csv, offline replay at 10 fps, 16 Oct 03:28 IST)

| Clip | Label | Plain: first fire (s) | Pose: first fire (s) | YOLO ms p50, plain / pose |
|---|---|---|---|---|
| v001.avi | fighting | 0.7 | 2.7 | 16.2 / 18.6 |
| v003.avi | fighting | 1.2 | 1.9 | 16.1 / 18.3 |
| v006.avi | fighting | 1.5 | 1.5 | 16.1 / 18.3 |
| v011.avi | fighting | 5.6 | 3.7 | 16.0 / 18.1 |
| v026.avi | fighting | never (max 1 person detected) | never | 15.6 / 17.9 |
| w001_masked.avi | fighting | 1.6 (person_down + fighting) | never | 15.8 / 18.1 |
| sample_bus.mp4 | normal | never (correct) | never (correct) | 19.2 / 22.1 |

Source: bench/results/ab_gate.csv.
Plain fires on 5 of 6 fight clips, pose on 4 of 6; plain is earlier on 3 clips, pose on 1, tie on 1. Neither fires on sample_bus. YOLO 15.6-22.1 ms per frame against the <= 40 ms target. The pipeline uses the plain model. This run predates the v1.14 gate change; its first-fire times match the offline gate check (6b) on every clip; neither matches the real-time run in section 5a (see the note there).

### 6b. Gate regression check (gate_check_p5.txt, 16 Oct 05:39 IST, M4)

Rule: every incident clip's gate for its labelled category must fire (for p3c, the one clip with an onset label, within a window around the onset; for the 6 clips without `onset_s` the check requires only that the gate fires at least once before the clip ends); normal and look-alike clips <= 2 gate-triggered calls per camera-minute ("limit 2.0"). Result: "gate check ok", exit 0. First fires: p3c 7.6 s (onset 5.6), v001 0.7, v003 1.2, v006 1.5, v011 5.6, w001_masked 1.6 (person_down:horizontal); v026 is a KNOWN MISS ("nano never detects both fighters, so no gate can fire; only a baseline can catch it"). Normal + look-alike clips: 2 gate calls in 2.0 camera-min = 0.98/min (limit 2.0): desk_closeup person_down @14.2 s, idle_60s fighting @31.1 s; floor_sit and sample_bus none. In the pipeline run (ab_p5_dev) floor_sit also fired once (fighting @16.5 s): 3 gate calls in 2.03 camera-min = 1.5/min, still under the limit.

Source: bench/results/gate_check_p5.txt; ab_p5_dev.csv (gate_fired, calls_p1 columns).

### 6c. Gate yield (SPEC §12: gate-triggered model calls / all model calls)

Computed from ab_p5_dev.csv as sum(calls_p1) / sum(calls_p1 + calls_p3) over the 11 rows: 9 / 61 = 14.8 %. Incident clips only: 6 / 26 = 23 %. Normal clips: 3 / 35 = 8.6 %. The clips are 3-60 s long and a baseline call runs every 3 s (`config.yaml vlm.baseline_interval_s`), so baselines dominate the count. The NFR-3 gate ablation (gates on vs periodic-only, same clips) has not been run.

Source: bench/results/ab_p5_dev.csv (calls_p1, calls_p3 columns).

### 6d. RTSP source (p5_rtsp.json, 16 Oct 05:51 IST, M4)

ffmpeg 8.0.1 has no RTSP listen mode, so `scripts/rtsp_sim.sh` serves a looping clip through a small stdlib RTSP server (`scripts/rtsp_sim.py`, fed by `ffmpeg -f rtp`). Added in Live mode as `rtsp://127.0.0.1:8554/live` (v011.avi looping, H.264 1280x720, 31.5 fps): tile status `live` 2.6 s after the add, first fighting alert 5.5 s after the add (the clip loops, so the fight starts anywhere in the loop: an upper bound), trigger -> alert 1281 ms, confidence 1.0, keep-up 0.969, YOLO 24.6 ms/frame at the alert.

Source: bench/results/p5_rtsp.json.

## 7. Chat (chat_runner, 16 Oct 07:09 IST)

Chat v2 (D75): the model writes every answer that has events, each sentence citing a stored event as [#id] (uncited sentences are dropped before the answer is shown); the model also reads the question when the rule parser finds no filter, finds nothing, or it is a follow-up. 48 questions against a seeded demo history in a temporary DB, "now" = 16 Oct 06:00 IST, idle GPU. Right 45 / 48. Invented events 0. Uncited sentences 0. Model-written answers 38 of 48: p50 2718 ms, p95 5870 ms, max 6942 ms; 3 over the NFR-1a 5 s target (missed on those). Model reading of the question: 14 questions, p50 2235 ms. Template fallbacks 0.

Misses: What did the man in red do?; Did anyone get hurt?; Any suspicious package?. The model's reading varies between runs on "injured" / "hurt" (the answer text named the right events; the key-frame strip listed more). "Any suspicious package?" (the stored events say backpack and suitcase) needs meaning-level search (local embeddings), planned next. Keyword search uses stemming (SQLite FTS5, Porter), so "pushed", "pushing" and "push" match; a detail the question asks for must still match, so "Anyone in a red jacket?" stays a grounded no.

Source: bench/results/chat_runner_summary.json, chat_runner.csv.

The brief's example and the four SPEC §13 questions (answers quoted from the csv, trimmed):
- "Show all tailgating events from camera 2 today" -> "No matching events (Cam2 · tailgating · 16 Oct 00:00–16 Oct 06:00 IST). No camera called cam2; cameras: Loading Dock, Lobby, Parking Lot, Server Room." (correct: this history has no camera 2)
- "What incidents happened in the last 10 minutes?" -> "2 events (16 Oct 05:50–16 Oct 06:00 IST): [#23] 16 Oct 05:56 · Lobby · person down (critical, 88%): A man collapses near the lift and does not get up. [#22] 16 Oct 05:52 · Loading Dock · suspicious activity / abandoned object (medium, 74%): An unattended suitcase sits beside the loading bay door."
- "How many falls today?" -> "2 events (person down · 16 Oct 00:00–16 Oct 06:00 IST): 2 person down. [#23] [#19]" (yesterday's person_down (fall) #8 correctly excluded)
- "Show fights on cam4" -> "No matching events (Cam4 · fighting · all time). No camera called cam4; cameras: Loading Dock, Lobby, Parking Lot, Server Room."
- "Anyone in a red jacket?" -> "No matching events (keywords: anyone red jacket · all time)." (the history has a blue jacket only; it was not returned)

Source: bench/results/chat_runner.csv (question, answer, right columns).

## 8. Round-1 checklist (SPEC §13)

| Item | Status | Evidence |
|---|---|---|
| M5: same Ollama + models, `uv sync`, camera permission, Continuity Camera, Wi-Fi off | partly done | iPhone + webcam seen streaming on the M5 (author's own check); Wi-Fi-off run pending (Aryan, M5); no results file |
| `./run_demo.sh` cold start < 2 min | M4: met, 10.2 s with Ollama killed first (5.7 s with Ollama already up); M5: pending (Aryan) | bench/results/p5_cold_start.json (Ollama app start + model load + re-seed + server + Chrome) |
| 3 cameras live, boxes visible, keep-up 100 % | pending on the M5 | M4 checked by eye with live sources; no results file |
| Staged fall on the high-mounted iPhone, filmed at 240 fps | not done | no person_down (fall) clip exists and no fall was staged yet; stand-in: the staged shove on the webcam, p3c_shove_sit_hug (fighting 1.000, onset-to-alert 3216 ms; ab_p5_dev.csv row 1) |
| Look-alikes -> no alert | recorded: met; live: pending | 0 alerts on floor_sit, desk_closeup, idle_60s, sample_bus (ab_p5_dev.csv); live on the iPhone pending |
| Recorded fight / fire / crowd clips -> correct cards | fights: 6 of 7 right; fire_smoke, crowd_incident: no clips | ab_p5_dev.csv; v026 gets a person_down card (wrong category) |
| Workflow view: stage timings + mosaic in real time | built (P3), checked by eye | no results file |
| Chat answers the 4 §13 questions, citing real events | met on seeded history | chat_runner.csv, last 4 rows; against the live demo DB pending |
| Metrics strip: YOLO ms, VLM p50/p95, model time-to-alert, GPU duty <= 60 % with 3 cameras | built (P3); duty target not met | 3 busy cameras 91-99.6 % (ab_run_duty_*_totals.json); 1 idle camera 53-56 % (ab_run_bus60_*_totals.json) |
| 10-min heat run on the M5, model time-to-alert drift < 25 % | pending (Aryan, M5) | no results file |
| 4B vs 2B decided on dev clips; veto log reviewed | 4B is the current default; final choice deferred to P6 (one normal clip only); veto log: counts logged per run, no review record | ab_model_summary.json (4/7 vs 5/7 on 6 fights + 1 normal clip); ab_run_*_totals.json, p2a_*.json (`vetoes_logged`, `vetoes_p_ge_0.3`) |

Source: files as named per row; rows without a file are the author's own checks, stated as such.

## 9. Pending, and how each will be measured

| Item | How | Owner |
|---|---|---|
| M5 cold start (`./run_demo.sh`, target < 2 min) | the M4 number is 10.2 s (bench/results/p5_cold_start.json); on the M5: stopwatch from the command to the dashboard up | Aryan (M5) |
| M5 latency re-run | the section 10 per-clip run on the M5, same 11 clips, same columns as ab_p5_dev | Aryan (M5) |
| 10-min heat run (model time-to-alert drift < 25 %) | 3 cameras on the M5 for 10 min, model time-to-alert logged over time | Aryan (M5) |
| Safari tile check | open the dashboard in Safari on the M5; confirm the v1.14 snapshot tiles paint | Aryan (M5) |
| Wi-Fi-off run (NFR-6) | the full demo with Wi-Fi off on the M5 | Aryan (M5) |
| Onset labels for the 6 public fight clips | fill `onset_s` in bench/labels.csv by eye, re-run ab_p5_dev, report onset-to-alert p50 / p95 | Riddhi |
| Test split | label held-out clips `test` in bench/labels.csv; judge on them, never tune on them (P8) | Riddhi (labels), captain (sign-off) |
| >= 30 min of normal footage | record idle and look-alike footage; report false alarms per camera-hour (SPEC §12) | Riddhi (collects), Abhinav (films) |
| Watts per camera | `sudo powermetrics --samplers cpu_power,gpu_power`, 60 s average, (N cameras - idle) / N (SPEC §12) | Aryan (M5) |
| Onset-to-alert live at 240 fps | one iPhone 240 fps video showing the staged incident and the dashboard toast | Abhinav |

Source: SPEC.md §4, §12, §13 for targets and methods. Owners from PLAN.md (validation owners).

## 10. Reproduce (M4, from the repo root)

- Gate regression check (CPU, exit 1 on failure): `uv run python -m bench.ab --gate --check`
- Chat question runner (48 questions, temp DB): `uv run python -m bench.chat_runner`
- Full pipeline on one or more clips (alerts, per-clip right/wrong, onset-to-alert ms, GPU duty): `uv run python -m app.pipeline <clip> [...]`
- The headline per-clip run that produced ab_p5_dev: `uv run python -c "from bench import ab; rows, tots = [], {}; ab.per_clip('v1.14_qwen3.5:4b-mlx', rows, tots); ab.report('p5_dev', rows, tots)"`
- Outputs land in bench/results/: `ab_<name>.csv` + `ab_<name>_summary.json`, `chat_runner.csv` + `chat_runner_summary.json`; the gate check prints to stdout (saved as gate_check_p5.txt).


## 11. Branch `fix/benchmark-metrics-v026`: metric correctness, v026 diagnosis, second look (16 Oct)

Machine for this section: a Linux x86 CPU sandbox (2 cores), **no vision model** (Ollama can't run there). Detector
numbers come from the real dev clips with `models/yolo26n.pt`; nothing here is a model accuracy or latency result.

### 11a. The historical F1, re-verified

Re-computed from the committed rows (`tests/test_metrics.py` asserts these):

| Run | Rows | fighting F1 | normal F1 | person_down F1 | Observed-label macro F1 |
|---|---|---|---|---|---|
| ab_p5_dev | 11 | 0.923 | 1.000 | 0.000 | **0.641** |
| ab_dev_p6 | 10 | 0.923 | 1.000 | 0.000 | 0.641 |
| ab_dev_p6b | 10 | 0.923 | 1.000 | 0.000 | 0.641 |

0.641 is the mean over the labels that appear as a truth **or** a prediction in those rows. person_down has no true
clip; it appears only because v026 was predicted person_down, so it scores 0 and pulls the mean down. The number is
kept unchanged under its old key (`macro_f1`, the dashboards read it) and under an explicit name
(`observed_label_macro_f1`). It is a **dev diagnostic**, comparable only with itself.

### 11b. Fixed 8-label evaluation (bench/metrics.py)

Over the canonical labels (`app.vlm.CATS`), on ab_dev_p6b: fighting P 1.00 / R 0.857 / F1 0.923 (7 clips), normal
1.00 / 1.00 / 1.00 (3 clips), person_down 0 clips and 1 false positive; fire_smoke, crowd_incident, property_damage,
suspicious_activity and tailgating: **0 clips**, listed, not hidden. Macro F1 over the 2 supported classes 0.962, over
all 8 classes 0.240 (a class without clips counts 0), weighted F1 0.946.

`final_metric_valid` is **false**: the split is dev, 6 classes have no test support, the historical runs carry no run
metadata. It becomes true only on a test split with every class supported, no test clip used for tuning and run
metadata present. `bench.validate` reports the gap: 10 labelled clips, all dev; dev covers fighting (7 clips,
1.16 min) and normal (3 clips, 1.53 min); 0 test clips; 1.53 of the 30 normal minutes SPEC §12 needs.

### 11c. v026, traced (bench/results/diag_v026_trace.json, diag_dev.json)

Detector replay of the real clip at 10 FPS, the same Detector + Scheduler code as the pipeline:

- **YOLO sees a person in 3 of 97 frames** (0.7, 0.8, 0.9 s; one track, conf 0.77 / 0.47 / 0.49), never two people,
  never a horizontal box. Motion (mean abs. difference of 160 px grey frames, 0.1 s apart) p90 is 1.8: in the range
  of the normal clips (idle_60s 1.34, floor_sit 2.14) and below every other fight clip (2.87-12.19).
- **The fighting gate cannot fire**: it needs two similar-height person boxes in contact; there is never a second box.
  The person_down gate cannot fire either: no horizontal box, no drop.
- **The verdict comes from a baseline call.** Detector-blind scenes use the empty-scene interval (10 s) and the
  change-gated skip, so the replay makes only 2 model calls in 9.7 s (t = 0.0 and 3.0 s). In p6b the alert came 4.4 s
  after clip start, consistent with the 3.0 s call.
- **What the model is told**: "up to 1 people in the last 4 s; trigger: none". No motion or interaction hint exists
  for it to use. The cross-check vetoes person_down only when the detector saw nobody in 4 s (D46): at t = 3.0 s it
  saw 1 person, so no veto.
- **No path distinguishes "down after a fight" from "a fall"**: both reach the model as one 2 s mosaic of a dark
  corridor with a person on the floor.
- **No detector-side signal can call v026 a fight**: to the detector it is an almost empty, low-motion room (no
  horizontal box, motion as low as the normal clips). A rule built from these signals would either miss v026 or alert
  on empty or quiet normal footage. What the detector CAN say is that it is blind here, which is what 11d uses.

### 11d. Proposed fix: person_down second look, alert-first (D83, pending captain)

**Alert first, correct in the open.** A person_down alerts exactly as on main (no added latency). If the detector
cannot vouch for it, the alert is marked unverified and a P4 second look runs over the whole 4 s buffer with a hint
naming the alternatives (fight / fall / lying normally). "Cannot vouch" = people seen in fewer than half of the buffer
frames (`detector_blind`), or a fighting gate fired in the buffer (`interaction`). The second look's verdict:

- **fighting** -> a fighting event opens (or the open one is used) and the person_down event is marked `dismissed`,
  `dismiss_reason: relook` (SPEC E-9). Nothing is rewritten or deleted: both rows stay in the DB and point at each
  other (`events.related_event_id`); the feed keeps both cards: "Re-checked: reclassified as Fighting #2" on the
  original, "Reclassified from Person down #1 after a re-check" on the new one. The fighting event's trigger -> alert
  is timed from the original trigger, so the correction's latency is reported honestly.
- **confident normal** (c >= 0.80) -> the person_down card is marked "Re-checked: the second look saw no incident".
- **anything else** -> the alert stands, marked confirmed.
- **no verdict** (stale P4 dropped after 6 s, verification window `verify_s` 10 s over, event already closed or
  dismissed by the operator, camera removed) -> the alert stands as it was; the late vote changes nothing.

While a fight that came from a re-label is open, another unverified person_down on that camera is the same incident
and does not alert again (`covered_by` in the log); a fall the detector vouches for still alerts. person_down is
never turned into fighting without a model vote for fighting. Every step is in the second-look log
(`GET /api/arbiter` `held_log`: unverified, relook, reclassified, retracted, verified, verify_expired, verify_moot,
relook_stale, relook_after_close, covered_by).

How often it would arm (bench.diagnose, real clips, every model call of the replay): v026 2 of 2 calls
(detector_blind); normal clips: sample_bus 0/4, idle_60s 1/19, floor_sit 4/8 (after its false fight-gate fire);
fight clips 1-6 per clip (interaction). It changes behaviour only where the model says person_down. First design
also counted any two overlapping boxes as interaction; replay showed that is true on almost every call of the
normal clips (idle_60s 19/19), so it was dropped. Plumbing verified end to end on v026 with a stand-in model that
answers person_down, then fighting on the second look (not a result, a wiring test): person_down #1 alerted at
441 ms, fighting #2 opened 1.7 s after the original trigger, #1 marked re-checked, both rows linked, both cards on
the dashboard; on p3c (detector vouches) the second look never arms.

**Not measured**: whether the real model's second look calls v026 fighting. If it answers a confident normal, v026
keeps its (wrong-category) alert in the history, marked re-checked, and the clip scores as a miss. Decide with the A/B on the Mac:
`bench.ab --dev --tag d83` vs `bench.ab --dev --tag d83off --no-down-guard`; adopt only if v026 improves and no
normal/look-alike clip gains an alert.

### 11e. Timing and measurement correctness

- p6b v006: the fight gate fired **500 ms before the labelled onset** (onset_to_gate -500 ms; onset_to_alert +810 ms).
  The onset label may be late. It is now reported as a timing warning (report tab + summary); a negative onset ->
  alert is excluded from the onset percentiles instead of being averaged.
- Latencies are wall-clock differences inside one process (`time.time()`, CLAUDE.md). Each run now checks the wall
  clock against the monotonic clock and flags the run (`timing_suspect`) if they drift > 50 ms.
- Offline replay (`--gate --check`, every 3rd frame in clip time) and live runs (latest frame at 10 Hz wall clock
  while the capture thread plays the file) sample different frames, so ByteTrack boxes and first-fire times differ
  (v011 2.5 s here vs 5.7 s in p6b). Every gate fire is now logged with frame index, detector time, clip time, rule,
  track ids, person count, score and outcome (submitted / merged / cooldown / silenced / too_soon) in both paths
  (`data/ab/<tag>/gate_log.jsonl`), so the two can be compared fire by fire. The gate check on this branch prints the
  same fires as before the change (gate_check_p6b.txt).
- Every dev pass now writes run metadata: commit, dirty tree, config hash, model and Ollama digest, machine, time,
  tag, split, repetitions (`meta` in the summary JSON). Historical runs have none (benchmark_metadata.json).

### 11f. Multi-camera instrumentation

`GET /api/arbiter` and every `bench.ab --run` now report: queue wait and run time by priority (p50/p95/max), cancelled
calls, stale drops, per-camera served count, queue wait and oldest waiting request (starvation), GPU duty per 10 s.
A stale P4 second look (> 6 s) is dropped explicitly and the alert it would have checked stands; P1s are never dropped,
P3 baselines build their mosaic at dispatch and are never stale. No throughput number changed on this branch: the
91-99.6 % duty with 3 busy cameras (section 5e) still stands until re-measured on the Mac with these counters.

### 11g. Tests and checks run on this branch

65 unit tests, stdlib unittest only (`uv run python -m unittest discover -s tests -t .`; pytest is not a dependency,
`pyproject.toml` only scopes its collection to `tests/` if someone runs it): metric modes incl. the 0.641
regression and zero-support classes; data validation incl. UTF-8 results files (fails on any read that relies on the
platform default encoding); the alert-first second look (27 cases: the immediate first alert, the later
reclassification with both rows linked, retraction, relook after close / operator dismissal / camera removal, stale
and duplicate relooks, repeated frames, two cameras, operator hold, old DB migration); the Report tab's accuracy
block on old / partial / odd files (no CSV, empty CSV, summary without `fixed`, unicode, zero and blank timings,
unknown labels); arbiter fairness / preemption / stale drops / duty timeline / JSON-serialisable `/api/arbiter` /
`duty()` under concurrent readers; scheduler de-duplication, gate-log fields, deterministic replay. `bench.metrics`,
`bench.validate` and `bench.ab` import without OpenCV or ultralytics. All module self-checks (vlm and server against a
stand-in model), `bench.validate`, `bench.ab --gate --check` pass; frontend builds. Run on Linux (cloud); the Mac
run is the one that counts.
