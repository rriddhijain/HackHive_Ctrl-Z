# HackHive: accuracy and latency report

Sat 17 Oct 2026, 00:45 IST. SPEC v1.22 (D86); D87 is merged but off by default (section 7).
Machine: every number below was measured on the dev machine M4 (Apple M4, 16 GB). Judging is on the demo machine M5 (Apple M5); nothing has been re-measured there yet.
Every number comes from a file under `bench/results/` (named under each block), a setting (`config.yaml`), a target (SPEC §4) or a label (`bench/labels.csv`). No number comes from a plan or an estimate (SPEC NFR-7).

## 1. In one minute

- **What it is.** YOLO26n + ByteTrack find people at 10 fps per camera. Cheap rules on their boxes (a fast drop or a box wider than tall, two boxes overlapping at speed, an abrupt background change) send that camera's last 2 s to a local vision model at once. A baseline call every 3 s (5 s with nobody in view) covers what no rule can see: fire, crowds, vandalism, theft. The model, Qwen3.5-4B (`qwen3.5:4b-mlx` via Ollama), sees a 2x2 letterboxed mosaic of 4 frames and gives a probability for each of 8 labels (fighting, person_down, fire_smoke, crowd_incident, tailgating, property_damage, suspicious_activity, normal) from its token log-probabilities. Event rules turn the probabilities into alerts stored in SQLite; the chat answers only from stored events. Fully local, no cloud.
- **Clips.** 31 clips covering 7 of the 8 labels (no tailgating clip). The split was fixed before any result: 16 dev clips (tuning) and 15 test clips (scored). The test split was not fully held out (section 3).
- **Accuracy, test (15 clips).** 4 of 15 clips right (3 before D86). Right: fire 2/2, crowd 1/1, theft 1/1. Wrong: falls 0/5, vandalism 0/4 (read as suspicious activity or a fall, or missed), a top-down bar fight (missed), and the one normal clip (a false person_down). 8 of 14 incident clips raised an alert of some category after the onset. Macro F1 over the fixed 8 labels (the NFR-2 form, target >= 0.75): 0.312 (0.250 before D86). This is not a valid final number: there is no tailgating clip, and the test clips were seen during tuning.
- **Accuracy, dev (16 clips, tuned on).** 9 of 16 right: fights 5/7, normal 3/3, crowd 1/2, fire 0/1, vandalism 0/3.
- **False alarms** (events on normal footage: any event on a normal clip, or one that opens more than 1 s before an incident's onset): test 3 in 4.5 camera-minutes (6 before D86); dev 2 in 3.1 camera-minutes. That is far too little normal footage for a per-hour rate (SPEC §12 needs >= 30 min).
- **Latency, fights** (onset -> alert, laptop cool, D86 settings, one clip at a time): 1.4, 2.4, 2.7, 3.1, 4.2 and 5.2 s on the 6 fights read right (of 7); p50 2.7 s. Target p95 <= 3.0 s: missed (with n = 6 the p95 is the max, 5.2 s). Before D86 the same clips took 0.8-4.1 s. This is the price of D86's fewer false alarms: a brief shove now alerts on the second look (p3c 1.3 -> 4.2 s). Sustained fights still alert on the first.
- **Latency, categories no rule can fire** (fire, crowd, theft; test pass, laptop hot): 7.0-9.9 s after the onset. They wait for baseline calls and a 3-look window.
- **Chat.** 45 of 48 questions right on a seeded history; 0 invented events, 0 uncited sentences.
- **How the parameters were set (D86).** One real pass records every model call. Thresholds are swept offline on the dev recordings (the replay is bit-exact with the live pass), prompt changes are re-asked on the recorded frames, and the choice is confirmed by one real pass. The thresholds turned out to sit on a plateau. What moved the numbers was what the model was told (the gate hint) and when it looked (the scheduler).
- **Waiting on one decision (D87).** A person_down second look, for when the detector can't vouch for the person (v026's case), is built and unit-tested but off. It needs one A/B pass with the real model.
- **Not measured.** Anything on the M5; tailgating; >= 30 min of normal footage; 3-camera latency since D86; watts per camera.

## 2. Definitions (SPEC §12)

| Term | Meaning |
|---|---|
| Onset | the first frame of the incident, by eye (`onset_s` in `bench/labels.csv`, clip seconds) |
| Onset -> alert | the alert's time minus the onset, on the clip clock: what a judge times. Includes the gate's delay, queue wait and baseline wait |
| Steady-state / mid-start | onset >= 2 s into the clip (`vlm.mosaic_span_s`) / earlier. A mid-start clip also times the first mosaic filling, which a running camera never does (SPEC v1.20) |
| Trigger -> alert | the alert's time minus the gate trigger (or the baseline request) |
| Clip prediction | the highest-confidence event opened from 1 s before the onset on (any event on a normal clip), else `normal`. Since 17 Oct 00:09 IST (8a5976e offline, 1eafc4a for live runs), an event that opens earlier is a false alarm, never a hit; earlier reports counted it as a hit |
| False alarm | an event on normal footage: any event on a normal clip, or one opened more than 1 s before an incident's onset |
| Wrong-category alert | an event after the onset whose category is not the clip's label |
| Macro F1, labels present | the historical `macro_f1` (`observed_label_macro_f1`): mean per-label F1 over the labels present as truth or prediction. A dev diagnostic, comparable only with itself |
| Macro F1, fixed 8 labels | `fixed.macro_f1_all8` (`bench/metrics.py`, D87): mean F1 over all 8 labels, a label with no clips counting 0. The NFR-2 form (target >= 0.75 on a held-out test set). `final_metric_valid` is true only on a test split with every label present, no clip used for tuning, and run metadata |
| Incident recall / precision | incident clips with any alert after the onset / incident clips; the same / clips with any alert |
| Gate | a rule on the person boxes that sends the camera's last 2 s to the model at once: `person_down` (a box top dropping fast, or a box wider than tall), `fighting` (two overlapping boxes moving >= 0.5 body heights/s), `scene_change` (`gate.*` in `config.yaml`) |
| Hint | the gate's numbers, sent with a gate call as labelled detector metadata (SPEC §7.4) |
| Veto | the detector contradicting the model's category (person_down or fighting when YOLO saw nobody), which halves its probability |

Source: SPEC.md §12, §4, §7.4; config.yaml; bench/ab.py (`replay`, `score_replay`, `score`); bench/metrics.py.

## 3. The clip set

| Clip | Label | Split | Source | Length (s) | Onset (s) |
|---|---|---|---|---|---|
| v001.avi | fighting | dev | public fight clip | 6.4 | 0.0 |
| v003.avi | fighting | dev | public fight clip | 3.0 | 0.0 |
| v006.avi | fighting | dev | public fight clip | 5.8 | 2.0 |
| v011.avi | fighting | dev | public fight clip | 8.7 | 1.0 |
| v026.avi | fighting | dev | public fight clip (an assault on a man on the floor) | 9.7 | 0.0 |
| w001_masked.avi | fighting | dev | public fight clip | 5.1 | 0.5 |
| p3c_shove_sit_hug.mp4 | fighting | dev | webcam: a staged shove, then a floor-sit and a hug as look-alikes | 30.0 | 5.6 |
| fight_ucf002.mp4 | fighting | test | UCF-Crime Fighting002 (a top-down bar camera) | 14.0 | 2.0 |
| fall_a_view2/5/6/7.mp4 | person_down | test | Montréal Multiple Cameras Fall Dataset, scene A: one fall from 4 ceiling angles; the person first lies down on a mattress on purpose (D84) | 35.2 / 34.8 / 35.3 / 25.9 | 23.0 |
| fall_b_view3.mp4 | person_down | test | the same dataset, scene B (D84) | 30.5 | 16.8 |
| fire_printer.mp4 | fire_smoke | dev | a printer giving off faint smoke (D86) | 50.0 | 18.0 |
| fire_bucket.mp4 / fire_room.mp4 | fire_smoke | test | two fire videos, trimmed around the first visible flame or smoke (D86) | 45.0 / 58.6 | 17.0 / 30.0 |
| crowd_timesq_a/b.mp4 | crowd_incident | dev | the Times Square panic, 2 angles (D86) | 46.5 / 43.5 | 22.0 / 6.5 |
| crowd_loveparade.mp4 | crowd_incident | test | the Love Parade crush (D86) | 50.0 | 0.0 |
| vandal_007/024/037.mp4 | property_damage | dev | UCF-Crime Vandalism (D86) | 32.0 / 32.0 / 45.0 | 9.0 / 20.0 / 12.0 |
| vandal_001/017/026/046.mp4 | property_damage | test | UCF-Crime Vandalism (D86) | 21.0 / 32.0 / 32.0 / 48.0 | 7.0 / 8.0 / 13.0 / 24.0 |
| theft_atm.mp4 | suspicious_activity | test | UCF-Crime Burglary013: two people prying an ATM open, already under way (D85) | 34.0 | 0.0 |
| sample_bus.mp4 | normal | dev | a street scene with a bus | 12.0 | - |
| idle_60s.mp4 | normal | dev | webcam, idle | 60.0 | - |
| floor_sit.mp4 | normal | dev | webcam look-alike: sitting on the floor | 20.0 | - |
| normal_room.mp4 | normal | test | 60 s of the fire_room video before the fire (D86) | 60.0 | - |

Source: bench/labels.csv (label, split, onset); data/ab/d86/rec/*.json (length); DECISIONS.md D84-D86 (sources); `bench.validate` passes on this set.

- Split rule (D86), fixed before any result: the sources sorted by their new names, alternating test, dev, test... within each category, with the two Times Square angles kept together. The falls and the theft were delivered as test clips (D84, D85).
- **The test split was not fully held out.** The base pass's test errors were read before the D86 fixes were chosen, and the hint variants were scored on all 29 gate calls, 12 of them test. On the 17 dev gate calls alone the choice is the same (section 5d). Treat the test numbers as a check on settings that were not tuned on them, not as a clean held-out estimate. A fresh clip set is the next held-out test.
- The UCF-Crime clips (vandalism, fight_ucf002, theft) are 1-3 s excerpts joined in index order without re-encoding, so they play as a time-lapse. Their onset is the first excerpt the dataset's own per-segment labels mark as abnormal. The fall onsets were read from frame sheets; Riddhi to verify.
- The 5 fall clips show 2 falls (scene A from 4 angles, scene B).
- Normal footage, as false alarms count it: 4.5 camera-minutes in test (normal_room plus the pre-onset part of the incident clips) and 3.1 in dev. The normal clips alone total 2.5 minutes. There is no tailgating clip, so tailgating is untested (dropped for now by the captain).

## 4. How the parameters are set (D86)

1. **Record.** `bench.ab --dev --tag T` (or `--test`) plays every clip once, alone, through the real pipeline, and records every model call to `data/ab/T/`: the probabilities, the detector evidence the cross-check uses, the hint, the mosaic and the times.
2. **Replay.** `--replay T` re-runs the cross-check and the event rules on the recordings with the current `config.yaml`, without the GPU. It is bit-exact against the live pass on all 16 dev clips.
3. **Sweep.** `--sweep T` moves each event threshold alone over a grid and chooses on dev only, by a rule fixed in advance: no more dev false alarms than now, then the highest dev macro F1, then the lowest onset -> alert, then the current value.
4. **Re-ask.** `--reask T` re-classifies the recorded mosaics after a prompt change (model only, about 1 s a call, no playback).
5. **Confirm** the choice with one real pass, then score the test split once.

What it found:
- **Thresholds: a plateau.** The sweep is flat on every grid, so no threshold changed. Its one non-tie pick, `open_single_critical` 0.65, was not confirmed by two live re-runs of p3c (first looks 0.42 and 0.25), so it was not adopted.
- **The hint biased the model.** "(possible fight)" made the model call a running crowd, a helper next to a fallen person, two men at an ATM and people talking fights. "(possible person down)" made it call people crouching person_down. The hint now names the look-alikes and leaves the call to the frames (section 5d).
- **The scheduler skipped a fall.** The change-gated baseline skipped 15 s right over a small, far fall: same track id, pixel change under the threshold. A baseline is now skipped only if no person's box moved >= 0.5 body heights or changed height or shape by >= 25 %. It is never skipped right after an incident reading that opened nothing, and never for more than 8 s (`vlm.baseline_skip.max_skip_s` 15 -> 8, `vlm.empty_interval_s` 10 -> 5).
- **The model never says property_damage.** On vandalism it answers normal or suspicious_activity (0 of 41 calls in the D86 pass, section 5c). The §6.1 wording now names kicking, hitting, smashing or spraying property; that did not change the outcome.

Source: DECISIONS.md D86; bench/ab.py (`record`, `replay`, `SWEEP`, `sweep`, `reask`); config.yaml.

## 5. Accuracy

### 5a. Test split, per clip

Each clip played once, alone, through the real pipeline (16 Oct; base pass 22:47-23:03 IST, D86 pass 23:19-23:36 IST, the laptop already warm). "@ s" is the clip time of the newest frame an alert was raised on; FA marks a false alarm.

| Clip | Label | Onset (s) | Before D86 (base pass) | D86 | D86 alerts: category @ s (peak) |
|---|---|---|---|---|---|
| crowd_loveparade.mp4 | crowd_incident | 0.0 | right, 4.4 s after onset | right, 7.0 s | crowd_incident @4.4 (0.91) |
| fall_a_view2.mp4 | person_down | 23.0 | fighting (1 FA) | fighting (1 FA) | person_down @13.8 (1.00, FA: the mattress look-alike); fighting @34.1 (1.00, the helpers) |
| fall_a_view5.mp4 | person_down | 23.0 | normal | normal | none |
| fall_a_view6.mp4 | person_down | 23.0 | normal (1 FA) | normal (1 FA) | person_down @20.2 (0.64, FA) |
| fall_a_view7.mp4 | person_down | 23.0 | normal (1 FA: fighting) | normal | none |
| fall_b_view3.mp4 | person_down | 16.8 | fighting | normal | none |
| fight_ucf002.mp4 | fighting | 2.0 | normal | normal | none |
| fire_bucket.mp4 | fire_smoke | 17.0 | right, 6.6 s | right, 8.0 s | fire_smoke @23.0 (0.98) |
| fire_room.mp4 | fire_smoke | 30.0 | right, 16.6 s | right, 9.9 s | fire_smoke @38.5 (0.99) |
| normal_room.mp4 | normal | - | fighting (3 FA) | person_down (1 FA) | person_down @33.0 (0.93, FA: a man bending with a cloth) |
| theft_atm.mp4 | suspicious_activity | 0.0 | fighting | right, 8.0 s | fighting @1.5 (0.78); suspicious_activity @5.4 (0.98) |
| vandal_001.mp4 | property_damage | 7.0 | person_down | person_down | person_down @15.9 (1.00, a person crouching) |
| vandal_017.mp4 | property_damage | 8.0 | suspicious_activity | suspicious_activity | suspicious_activity @12.8 (0.87) |
| vandal_026.mp4 | property_damage | 13.0 | suspicious_activity | suspicious_activity | suspicious_activity @20.7 (0.98) |
| vandal_046.mp4 | property_damage | 24.0 | suspicious_activity | normal | none |

| Test totals | Before D86 | D86 |
|---|---|---|
| Clips right | 3 / 15 | 4 / 15 |
| False alarms on normal footage (4.5 camera-min) | 6 | 3 |
| Wrong-category alerts | 7 | 5 |
| Incident clips with any alert after the onset (recall) | 10 / 14 | 8 / 14 |
| Clips with any alert that were incidents (precision) | 10 / 11 | 8 / 9 |
| Macro F1, labels present | 0.286 | 0.357 |
| Macro F1, fixed 8 labels (`final_metric_valid`: false) | 0.250 | 0.312 |

Source: bench/results/ab_replay_base.txt, ab_replay_d86.txt (`bench.ab --replay`, bit-exact with the live passes); ab_test_base.csv, ab_test_d86.csv and their `_summary.json` (`fixed` block).

The D86 gain is fewer false fights: on the fall clips, the theft and the normal room. Most of the base pass's extra "incident" alerts were those false fights. That is why incident recall fell from 10 to 8 of 14 while false alarms halved.

### 5b. Dev split, per clip

| Clip | Label | Onset (s) | Before D86 | D86 | D86 alerts: category @ s (peak) |
|---|---|---|---|---|---|
| crowd_timesq_a.mp4 | crowd_incident | 22.0 | normal (1 FA) | normal (1 FA) | crowd_incident @5.0 (0.90, FA: 17 s before the panic) |
| crowd_timesq_b.mp4 | crowd_incident | 6.5 | fighting (1 FA) | right | crowd_incident @15.8 (0.81) |
| fire_printer.mp4 | fire_smoke | 18.0 | normal | normal | none (faint smoke) |
| floor_sit.mp4, idle_60s.mp4, sample_bus.mp4 | normal | - | right | right | none |
| p3c_shove_sit_hug.mp4 | fighting | 5.6 | right | right | fighting @8.6 (1.00); fighting @23.8 (0.82, during the hug) |
| v001.avi, v003.avi, v006.avi, v011.avi | fighting | 0.0-2.0 | right | right | fighting, one alert each |
| v026.avi | fighting | 0.0 | person_down | person_down | person_down @3.1 (0.93) |
| w001_masked.avi | fighting | 0.5 | right | person_down | person_down @1.7 (0.96) |
| vandal_007.mp4 | property_damage | 9.0 | suspicious_activity | suspicious_activity | suspicious_activity @20.0 (0.69) |
| vandal_024.mp4 | property_damage | 20.0 | normal | normal | none |
| vandal_037.mp4 | property_damage | 12.0 | person_down (1 FA) | person_down (1 FA) | person_down @8.0 (0.90, FA); person_down @41.3 (0.84) |

| Dev totals | Before D86 | D86 |
|---|---|---|
| Clips right | 9 / 16 | 9 / 16 |
| False alarms on normal footage (3.1 camera-min) | 3 | 2 |
| Wrong-category alerts | 5 | 4 |
| Macro F1, labels present | 0.218 | 0.310 |
| Macro F1, fixed 8 labels | 0.191 | 0.271 |

Source: bench/results/ab_replay_base.txt, ab_replay_d86.txt; ab_dev_base.csv, ab_dev_d86.csv and their `_summary.json`.

- w001_masked flips between identical settings: person_down in the D86 pass, fighting in the cool re-time (section 6a). Run-to-run variance is 1-2 clips, because which frames land in each mosaic depends on the wall clock.
- p3c alerts fighting a second time during the hug. The clip-level rule does not count it, as it comes after the onset, but on a live camera it would be a false alarm.
- The D86 dev latencies are not quoted: that pass ran after 45 minutes of GPU load (section 6c).

### 5c. The model's own skill, per call (before any event rule)

Every model call in the D86 pass (252 calls, 31 clips): true label -> the model's top category. A call's true label is the clip's label once its newest frame is past the onset, else normal.

| True label | Calls | Model's top category |
|---|---|---|
| normal | 123 | normal 99, person_down 11, suspicious_activity 7, crowd_incident 5, fighting 1 |
| property_damage | 41 | normal 26, suspicious_activity 12, person_down 3 |
| crowd_incident | 27 | crowd_incident 18, normal 7, fighting 2 |
| fighting | 22 | fighting 9, normal 7, person_down 5, suspicious_activity 1 |
| person_down | 16 | normal 9, person_down 6, fighting 1 |
| fire_smoke | 14 | fire_smoke 9, normal 5 |
| suspicious_activity | 9 | suspicious_activity 8, fighting 1 |

Source: bench/results/ab_replay_d86.txt (per-call confusion); before D86: ab_replay_base.txt (228 calls).

149 of 252 calls are right (134 of 228 before D86). On normal footage, 24 of 123 calls named an incident; the event rules (corroboration, the 3-look window, the vetoes) turned them into 5 false alarms. The model never answers property_damage. A fight's calls include lulls inside the incident, so the per-call figure is a lower bound.

### 5d. The hint experiment (the D86 change that mattered)

The base pass's recorded mosaics, re-asked with each hint (model only). Gate calls only, since the hint is sent only with them.

| Hint sent with a gate call | All (29) | Dev (17) | Test (12) |
|---|---|---|---|
| "(possible fight)" / "(possible person down)" (before D86) | 5 | 4 | 1 |
| none: the rule's numbers only | 8 | 5 | 3 |
| **the look-alikes, e.g. "(a fight, or people hugging, helping someone up, working side by side, or a crowd moving: judge from the frames)" (adopted)** | **14** | **10** | **4** |
| the same + the new §6.1 wording, every call re-asked | 13 | 9 | 4 |

Also tried and not adopted: with nobody in view, the newest frame alone at 576x320 instead of the 2x2 grid (23 of 31 calls right, vs 24 of 31).

Source: bench/results/hint_variants_d86.txt (from data/ab/base/reask_*.json).

### 5e. What is still wrong, and why

- **Falls, 0 of 5 after the onset.** Scene A opens with a deliberate look-alike, someone lying down on a mattress. The model calls it person_down 3-9 s before the real fall. That open event then runs on through the fall, so an operator does see person_down during it, but it began on the look-alike. view5: the model saw the real fall once (0.66), but YOLO-nano saw nobody (a person lying down), so the person_down veto cut it. Every fall is a test clip, so the veto was not tuned. view7: the fall comes 2.9 s before the clip ends. b_view3: missed.
- **Vandalism, 0 of 7.** It is filed as suspicious_activity (an operator still gets an alert, under the wrong label) or missed. vandal_001 shows a person crouching and is read as person_down.
- **fight_ucf002**: a top-down bar camera, read as normal. **v026**: an assault on a man on the floor, read as person_down (section 7). **fire_printer**: faint smoke, missed. **normal_room**: a man bending with a cloth, read as person_down.
- **Tailgating**: no clip, untested.

## 6. Latency

Targets (SPEC §4 NFR-1): onset -> alert p95 <= 3.0 s for gate-triggered categories; model time-to-alert p95 <= 2.0 s; YOLO <= 40 ms a frame. The headline is onset -> alert, the number a judge times.

### 6a. Fights: onset -> alert, laptop cool, one clip at a time (ms)

| Clip | Onset (s) | Group | Before D86 | D86 (cool re-time) | D86 trigger -> alert |
|---|---|---|---|---|---|
| p3c_shove_sit_hug.mp4 | 5.6 | steady-state | 1259 | 4239 | 1190 |
| v006.avi | 2.0 | steady-state | 797 | 5163 | 1977 |
| v001.avi | 0.0 | mid-start | 2362 | 2427 | 1640 |
| v003.avi | 0.0 | mid-start | 3001 | 2675 | 1386 |
| v011.avi | 1.0 | mid-start | 2443 | 1381 | 1794 |
| w001_masked.avi | 0.5 | mid-start | 4063 | 3116 | 1335 |
| v026.avi | 0.0 | - | person_down | person_down | - |
| **6 fights** | | | **p50 2362, max 4063; 4 of 6 within 3.0 s** | **p50 2675, max 5163; 3 of 6 within 3.0 s** | |

Source: before D86: bench/results/ab_replay_base.txt (onset -> alert per clip; bit-exact with the base pass, run cool at the start of the evening). D86: ab_run_cool_<clip>.csv and `_totals.json` (one `bench.ab --run` per clip, 16 Oct 23:41-23:44 IST, after the laptop had cooled).

- **Target p95 <= 3.0 s: missed** both before and after D86. With 6 alerts the p95 is the max.
- **D86 made brief shoves slower.** The look-alike hint lowers the first look's confidence on a short shove (p3c's first look: 0.94 with the old hint, 0.25-0.61 with the new one), so it alerts on the second look. On v006, the first gate call came before the labelled onset and no longer opens an event; the next gate does. In the base pass that gate fired 500 ms before the labelled onset (a `timing_warnings` entry in ab_dev_base_summary.json), so the label may be late. Sustained fights still alert on the first look, at 0.94-1.00.
- Model time-to-alert (newest frame -> category known), p50 per clip in the cool re-time: 1236-1441 ms. YOLO stays far under its 40 ms budget (15.6-24.6 ms a frame, section 11).

### 6b. Categories no rule can fire (test split, D86 pass, laptop hot)

crowd_loveparade 7.0 s (mid-start), theft_atm 8.0 s (mid-start), fire_bucket 8.0 s, fire_room 9.9 s. No gate exists for fire, crowds, vandalism or theft, so they wait for baseline calls (every 3 s per camera) and the 3-look window (mean >= 0.55, or >= 0.50 for crowd_incident, property_damage and suspicious_activity). Before D86: crowd 4.4 s, fire 6.6 and 16.6 s.

Source: bench/results/ab_replay_d86.txt, ab_replay_base.txt; config.yaml (`events.open_window`, `events.open_window_ungated`, `vlm.baseline_interval_s`).

### 6c. Heat

The D86 passes ran after about 45 minutes of GPU load. Trigger -> alert p50 on the dev clips read right: 1313 ms in the base pass, 2137 ms in the D86 pass, and 1386 ms when the D86 settings were re-timed cool (the 6 fights read right, 1190-1977 ms). A long run slows every call, so the demo should start on a cool machine.

Source: bench/results/ab_dev_base_summary.json, ab_dev_d86_summary.json (`trigger_to_alert_p50_p95`); ab_run_cool_*_totals.json.

### 6d. GPU duty

One clip at a time, the mean is 68 % (base dev), 74 % (D86 dev), 63 % (base test) and 70 % (D86 test). The 3-camera duty was last measured before D86: 91-99.6 % with 3 busy cameras against a target of <= 60 % (section 11). That is why the demo plays clips one at a time. D86 makes baselines skip less, so the 3-camera figure is unlikely to be lower now; it has not been re-measured.

Source: bench/results/ab_{dev,test}_{base,d86}_summary.json (`gpu_duty_mean`).

## 7. v026 and the person_down second look (D87, merged, off by default)

From teammate Aryan's branch `fix/benchmark-metrics-v026`, ported as D87. Detector-only work; no vision-model number below.

- **v026, traced on the real clip** (the same Detector + Scheduler code, 10 fps): YOLO sees a person in 3 of 97 frames, never two people and never a box wider than tall. Motion p90 is 1.8, as low as the normal clips (idle_60s 1.34, floor_sit 2.14) and below every other fight clip (2.87-12.19). So no gate can fire, and the verdict comes from a baseline call. No detector signal can call v026 a fight without also alerting on quiet normal footage; what the detector can say is that it is blind there.
- **The second look** (`events.down_guard`). A person_down alerts at once, as now. If the detector can't vouch for it (people in fewer than half of the buffer's frames, or a fighting gate in the buffer), a low-priority re-look over 4 s corrects it in the open. A fighting verdict opens a fighting event and marks the person_down re-checked; both rows stay and link to each other. A confident normal marks the alert re-checked. Anything else confirms it.
- **Status: off** (`events.down_guard.enabled: false`). It is unit-tested (65 tests) and wired end to end with a stand-in model, which is a wiring test, not a result. It is adopted only if a dev A/B with the real model (`bench.ab --dev --tag d87 --down-guard` against the D86 pass) improves v026 and adds no alert on a normal or look-alike clip. The Next.js dashboard does not show the "Re-checked" card yet.

Source: bench/results/diag_v026_trace.json, diag_dev.json; DECISIONS.md D87; config.yaml (`events.down_guard`).

## 8. Gates (gate_check_d86.txt, 16 Oct 23:19 IST, after D86)

Rule: every incident clip's gate for its labelled category must fire around the onset, and normal and look-alike clips make <= 2 gate-triggered calls per camera-minute. Result: "gate check ok", exit 0.
- Normal + look-alike clips: 2 gate calls in 1.5 camera-minutes, 1.31 a minute (limit 2.0): floor_sit fighting @5.7 s, idle_60s fighting @31.0 s, sample_bus none.
- First fires: p3c 5.5 s (onset 5.6), v001 0.7, v003 1.2, v006 1.5, v011 2.0, w001_masked 1.6 (person_down for a box wider than tall, and fighting).
- v026 is a known miss: YOLO-nano never sees both fighters, so only a baseline can catch it (section 7).
- The fighting gate also fires on the running Times Square crowd and during vandal_037. The look-alike hint is what keeps those calls from becoming fights.

Source: bench/results/gate_check_d86.txt.

## 9. Chat (chat_runner, 16 Oct about 23:50 IST, laptop warm)

48 questions against a seeded demo history in a temporary database. Right 45 of 48. Invented events 0, uncited sentences 0. Model-written answers 38: p50 2610 ms, p95 6661 ms, max 9677 ms; 4 over the 5 s target (NFR-1a). The model read the question itself on 14 of them (p50 2086 ms).

Misses:
- "What did the man in red do?": a grounded no, but given as a detail answer, not the expected summary.
- "Did anyone get hurt?": the text names the right 3 events, but the key-frame strip lists 20.
- "Any suspicious package?": the events say backpack and suitcase; this needs meaning-level search.

The brief's example, "Show all tailgating events from camera 2 today", gets: "No matching events (Cam2 · tailgating · 16 Oct 00:00–16 Oct 06:00 IST). No camera called cam2; cameras: Loading Dock, Lobby, Parking Lot, Server Room. The same on other cameras (1): [#20] 16 Oct 05:05 · Lobby · tailgating (medium, 86%): A courier follows a staff member through the main door on one swipe."

Source: bench/results/chat_runner.csv, chat_runner_summary.json.

## 10. Measurement checks (D87)

- `bench.validate` checks labels, files, splits, onsets and result files, and exits 1 on a problem. It passes on the current set.
- Every new pass writes run metadata (commit, dirty tree, config hash, model digest, machine, time) and checks the wall clock against the monotonic clock (`timing_suspect` if they drift > 50 ms). The base and D86 passes predate this, so their summaries carry no metadata.
- An alert or gate before the labelled onset is listed under `timing_warnings` and kept out of the onset -> alert percentiles.
- Every gate fire is logged with frame, clip time, rule, persons and outcome (`data/ab/<tag>/gate_log.jsonl`), and `GET /api/arbiter` reports queue wait by priority, stale drops and per-camera starvation, for the next 3-camera run.
- 65 stdlib unit tests: `uv run python -m unittest discover -s tests -t .`

Source: DECISIONS.md D87; bench/validate.py; bench/metrics.py; tests/.

## 11. Earlier measurements (before D86; still valid as measured)

- **Model and layout A/B** (7 clips, 16 Oct 03:05-03:20 IST, older gates): 4B 4/7 vs 2B 5/7, with the same incident recall (0.667); the 4B was 285 ms faster at p50 (1207 vs 1492 ms trigger -> alert). The 2x2 mosaic was kept over native video: native video got one more clip right but was 1.9x slower at p50 and ran the GPU at 97 %. Source: ab_model_summary.json, ab_tiles_summary.json.
- **The first headline run** (11 clips, fighting and normal only, 16 Oct 05:35 IST): 10 of 11 right; its labels-present macro F1 of 0.641 was re-verified on three runs by D87. It is a dev diagnostic, not comparable with the numbers above. Source: ab_p5_dev_summary.json; tests/test_metrics.py.
- **Model only, P0** (15 Oct 21:52-21:54 IST; excludes gate, queue and capture, so never quoted as alert latency; seconds):

  | Model | Tile | Category token p50 / p95 | Full call p50 / p95 |
  |---|---|---|---|
  | qwen3.5:4b-mlx | 160 | 1.603 / 2.190 | 3.539 / 4.357 |
  | qwen3.5:4b-mlx | 224 | 1.740 / 2.004 | 3.679 / 4.085 |
  | qwen3.5:2b | 160 | 1.229 / 1.797 | 2.305 / 3.594 |
  | qwen3.5:2b | 224 | 1.347 / 1.455 | 2.437 / 2.612 |

  Source: latency_p0_tile160.json, latency_p0_tile224.json. The pipeline uses 288x160 tiles, not measured in this form.
- **Store -> card** (browser): p50 13.0 ms, p95 20.2 ms, n = 2 (budget <= 100 ms). Source: p5_cold_start.json.
- **Cold start**, `./run_demo.sh` on the M4: 10.2 s with Ollama killed first (target < 2 min). Source: p5_cold_start.json.
- **GPU duty, 3 cameras** (16 Oct 03:2x IST): 1 idle camera 53-56 %; 3 static cameras 39 %; 3 cameras with people moving 91-99.6 % (target <= 60 %: missed). Source: ab_run_bus60_*, ab_run_duty_*_totals.json, p2a_duty_static_x3.json.
- **Plain vs pose YOLO for the fight gate** (offline, 10 fps): plain fires on 5 of 6 fight clips, pose on 4; YOLO 15.6-22.1 ms a frame. Source: ab_gate.csv.
- **RTSP source**: the tile went live 2.6 s after adding `rtsp://127.0.0.1:8554/live`; trigger -> alert 1281 ms; YOLO 24.6 ms a frame. Source: p5_rtsp.json.

## 12. Pending, and how each will be measured

| Item | How | Owner |
|---|---|---|
| M5: cold start, latency re-run, 10-min heat run, Safari, Wi-Fi off | `./run_demo.sh` stopwatch; `bench.ab --dev --tag m5` (+ `--test`); 3 cameras for 10 min | Aryan (M5) |
| The second look (D87) | `bench.ab --dev --tag d87 --down-guard` vs the D86 pass; adopt only if v026 improves and no normal clip gains an alert | captain decides, Aryan runs |
| A held-out test | a fresh clip set, labelled before any run, scored once | Riddhi (labels), captain |
| >= 30 min of normal footage | record idle and look-alike scenes; report false alarms per camera-hour | Riddhi, Abhinav |
| Falls | a staged fall on the high-mounted iPhone at 240 fps; review the person_down veto for people lying down | Abhinav |
| 3-camera duty and latency since D86 | `bench.ab --run a b c --seconds 60` (with the D87 arbiter counters) | Aryan (M5) |
| Tailgating | a door clip with a zone (SPEC v1.15) | dropped for now (captain) |
| Watts per camera | `sudo powermetrics --samplers cpu_power,gpu_power`, 60 s average | Aryan (M5) |

## 13. Reproduce (from the repo root)

- Gate regression check (CPU, exit 1 on failure): `uv run python -m bench.ab --gate --check`
- Data and results validation: `uv run python -m bench.validate`
- Re-score a recorded pass offline (CPU): `uv run python -m bench.ab --replay d86` (or `base`)
- Threshold sweep on the dev recordings: `uv run python -m bench.ab --sweep d86`
- A new recorded pass (GPU, about 10 min each): `uv run python -m bench.ab --dev --tag T`, then `--test --tag T`
- One clip, cool re-time: `uv run python -m bench.ab --run data/dev/fighting/v006.avi --tag cool_v006`
- Chat questions (temporary DB): `uv run python -m bench.chat_runner`
- Unit tests: `uv run python -m unittest discover -s tests -t .`
- Recordings live in `data/ab/<tag>/` (not committed); results in `bench/results/`.
